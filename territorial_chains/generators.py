"""Activity-chain generators with one interface, so they can be scored on one grid.

Every generator learns from survey respondents (``fit``) and then proposes a
chain for each target person from that person's attributes alone (``sample``):

``MatchingGenerator``         eqasim's statistical matching, called unchanged
``BayesNetGenerator``         a Bayesian network over attributes and chain structure,
                              in the spirit of Joubert and de Waal (2020)
``AutoregressiveGenerator``   a small causal transformer that writes the chain one
                              activity at a time, conditioned on the attributes
``VAEGenerator``              a conditional variational autoencoder: a latent vector
                              summarises the whole day and a recurrent decoder writes it
``GANGenerator``              a conditional Wasserstein GAN that writes all positions of
                              the chain at once from a noise vector

The optional dependencies (pgmpy, torch, an eqasim checkout) are imported only
by the generator that needs them.
"""

import sys

import numpy as np
import pandas as pd

ATTRIBUTES = ["sex", "any_cars", "age_class", "socioprofessional_class", "urban_type"]
ALPHABET = "hweslo"
SECONDARY = set("slo")


def _normalised_weights(frame):
    w = frame["weight"].to_numpy(dtype=float)
    return w * len(w) / w.sum()


# --------------------------------------------------------------------------- matching

class MatchingGenerator:
    """eqasim's ``statistical_matching`` (synthesis/population/matched.py), unchanged.

    ``columns`` is the ordered attribute list: when a cell holds fewer than
    ``minimum_observations`` donors, attributes are dropped from the end.
    """

    def __init__(self, eqasim_path, columns, minimum_observations=20):
        self.eqasim_path, self.columns, self.minimum = eqasim_path, list(columns), minimum_observations

    def fit(self, train):
        if self.eqasim_path not in sys.path:
            sys.path.insert(0, self.eqasim_path)
        from synthesis.population.matched import statistical_matching
        self._match = statistical_matching
        self.source = train[["person_id", "weight", "chain"] + self.columns].rename(
            columns={"person_id": "donor_id"}).copy()
        return self

    def sample(self, target, rng):
        class Progress:
            def update(self, n): pass

        frame = target[self.columns].copy()
        frame["target_id"] = np.arange(len(frame))
        assignment, levels = self._match(
            Progress(), self.source, "donor_id", "weight", frame, "target_id", list(self.columns),
            random_seed=int(rng.integers(1 << 30)), minimum_observations=self.minimum)
        chains = assignment.merge(self.source[["donor_id", "chain"]], on="donor_id").sort_values("target_id")
        self.last_levels = levels
        return chains["chain"].to_numpy()


# --------------------------------------------------------------------------- Bayesian network

def chain_structure(chains):
    """Four discrete descriptors of a chain; together they define its structural class.

    Whether the person goes out at all is its own binary variable. Territory
    acts mostly there, and a binary node lets the structure search attach
    territory to it for a handful of parameters instead of a full table.
    """
    chains = pd.Series(chains).reset_index(drop=True)
    inner = chains.str.strip("h")
    tours = np.where(inner == "", 0, inner.str.count("h+") + 1)
    return pd.DataFrame({
        "mobile": np.where(chains.str.len() == 1, "no", "yes"),
        "primary": np.select(
            [chains.str.len() == 1, chains.str.contains("w"), chains.str.contains("e")],
            ["none", "work", "education"], default="other"),
        "tours": np.minimum(tours, 3).astype(str),
        "secondary": np.minimum(chains.apply(lambda c: sum(ch in SECONDARY for ch in c)), 3).astype(str),
    })


class BayesNetGenerator:
    """Bayesian network over person attributes and chain structure.

    The graph is found by score-based search (pgmpy, hill climbing on BIC) with
    one constraint: chain variables cannot be parents of person attributes.
    Conditional tables are weighted counts with a Dirichlet prior centred on the
    marginal, so a sparse parent configuration falls back smoothly instead of
    dropping an attribute outright. A concrete chain is then drawn among the
    survey chains of the sampled structural class.

    The step that statistical matching does with cells of at least 20 donors is
    done here by factorisation: territory can act on one chain variable without
    requiring donors for every combination of all attributes.
    """

    CHAIN_NODES = ["mobile", "primary", "tours", "secondary"]

    def __init__(self, attributes=ATTRIBUTES, required_edges=(), prior_strength=5.0, max_indegree=4, seed=0):
        self.attributes, self.alpha, self.max_indegree, self.seed = list(attributes), prior_strength, max_indegree, seed
        self.required = list(required_edges)     # edges imposed by the modeller, e.g. ("urban_type", "mobile")

    def fit(self, train):
        from pgmpy.estimators import HillClimbSearch, ExpertKnowledge

        data = pd.concat([train[self.attributes].astype(str).reset_index(drop=True),
                          chain_structure(train["chain"])], axis=1)
        weights = _normalised_weights(train)

        # Structure search on a weight-proportional resample, so the graph reflects the population.
        rng = np.random.default_rng(self.seed)
        resample = data.iloc[rng.choice(len(data), size=len(data), p=weights / weights.sum())]
        forbidden = [(c, a) for c in self.CHAIN_NODES for a in self.attributes]
        forbidden += [(a, b) for a in self.attributes for b in self.attributes if a != b]
        # Going out or not is decided first; the other chain variables describe the day of those who do.
        forbidden += [(c, "mobile") for c in self.CHAIN_NODES if c != "mobile"]
        dag = HillClimbSearch(resample).estimate(
            scoring_method="bic-d",
            expert_knowledge=ExpertKnowledge(forbidden_edges=forbidden, required_edges=self.required),
            max_indegree=self.max_indegree, show_progress=False)
        self.edges = sorted(dag.edges())

        parents = {n: sorted(p for p, c in self.edges if c == n) for n in self.CHAIN_NODES}
        self.order, self.parents = self._topological(parents), parents

        # Weighted conditional tables with a Dirichlet prior centred on the marginal.
        self.tables = {}
        for node in self.CHAIN_NODES:
            states = sorted(data[node].unique())
            marginal = pd.Series(weights).groupby(data[node].to_numpy()).sum().reindex(states, fill_value=0.0)
            marginal = (marginal / marginal.sum()).to_numpy()
            if parents[node]:
                key = data[parents[node]].agg("|".join, axis=1).to_numpy()
                counts = pd.crosstab(key, data[node].to_numpy(), values=weights, aggfunc="sum").reindex(columns=states).fillna(0.0)
                probs = (counts.to_numpy() + self.alpha * marginal) / (counts.to_numpy().sum(axis=1, keepdims=True) + self.alpha)
                table = dict(zip(counts.index, probs))
            else:
                table = {}
            self.tables[node] = (states, marginal, table)

        # Concrete chains available inside each structural class.
        klass = data[self.CHAIN_NODES].agg("|".join, axis=1).to_numpy()
        pool = pd.DataFrame({"klass": klass, "chain": train["chain"].to_numpy(), "weight": weights})
        self.pools = {k: (g["chain"].to_numpy(), g["weight"].to_numpy() / g["weight"].sum())
                      for k, g in pool.groupby("klass")}
        self.all_chains = (pool["chain"].to_numpy(), pool["weight"].to_numpy() / pool["weight"].sum())
        return self

    def _topological(self, parents):
        order, remaining = [], list(self.CHAIN_NODES)
        while remaining:
            for node in remaining:
                if all(p not in remaining for p in parents[node] if p in self.CHAIN_NODES):
                    order.append(node)
                    remaining.remove(node)
                    break
            else:
                raise RuntimeError("cycle among chain variables")
        return order

    def sample(self, target, rng):
        frame = target[self.attributes].astype(str).reset_index(drop=True)
        for node in self.order:
            states, marginal, table = self.tables[node]
            if self.parents[node]:
                key = frame[self.parents[node]].agg("|".join, axis=1).to_numpy()
                drawn = np.empty(len(frame), dtype=object)
                for value in np.unique(key):
                    mask = key == value
                    drawn[mask] = rng.choice(states, size=mask.sum(), p=table.get(value, marginal))
                frame[node] = drawn
            else:
                frame[node] = rng.choice(states, size=len(frame), p=marginal)

        klass = frame[self.CHAIN_NODES].agg("|".join, axis=1).to_numpy()
        chains = np.empty(len(frame), dtype=object)
        for value in np.unique(klass):
            mask = klass == value
            pool, p = self.pools.get(value, self.all_chains)
            chains[mask] = rng.choice(pool, size=mask.sum(), p=p)
        return chains


# --------------------------------------------------------------------------- autoregressive

class _TokenCoding:
    """Chains as token sequences (0 pad, 1 begin, 2 end, 3.. activities) and attributes as integer codes."""

    def _encode(self, chains):
        import torch
        index = {c: i + 3 for i, c in enumerate(ALPHABET)}
        out = np.zeros((len(chains), self.max_length + 2), dtype=np.int64)
        for row, chain in enumerate(chains):
            tokens = [1] + [index[c] for c in chain[:self.max_length]] + [2]
            out[row, :len(tokens)] = tokens
        return torch.from_numpy(out)

    def _attributes(self, frame):
        import torch
        columns = [frame[a].astype(str).map(self.levels[a]).fillna(0).astype(int).to_numpy() for a in self.attributes]
        return torch.from_numpy(np.stack(columns, axis=1))

    @staticmethod
    def _decode(tokens):
        letters = np.array(list("???" + ALPHABET))
        out = []
        for row in tokens:
            chain = "".join(letters[t] for t in row if t >= 3)
            out.append(chain if chain else "h")
        return np.array(out, dtype=object)


class AutoregressiveGenerator(_TokenCoding):
    """A small causal transformer writing the chain one activity at a time.

    Person attributes are embedded and added to every position, so each next
    activity is predicted from the attributes and the activities so far. Unlike
    the two other generators it can write chains no respondent reported.
    """

    def __init__(self, attributes=ATTRIBUTES, d_model=64, layers=2, heads=4, max_length=16,
                 epochs=25, batch_size=256, learning_rate=3e-3, dropout=0.1, seed=0):
        self.attributes = list(attributes)
        self.d_model, self.layers, self.heads, self.max_length = d_model, layers, heads, max_length
        self.epochs, self.batch_size, self.lr, self.dropout, self.seed = epochs, batch_size, learning_rate, dropout, seed

    def _build(self):
        import torch
        from torch import nn

        d, n_attr = self.d_model, len(self.attributes)
        sizes = [len(self.levels[a]) + 1 for a in self.attributes]

        class Model(nn.Module):
            def __init__(inner):
                super().__init__()
                inner.token = nn.Embedding(len(ALPHABET) + 3, d, padding_idx=0)
                inner.position = nn.Embedding(self.max_length + 2, d)
                inner.attribute = nn.ModuleList([nn.Embedding(s, d) for s in sizes])
                layer = nn.TransformerEncoderLayer(d, self.heads, 4 * d, self.dropout, batch_first=True, norm_first=True)
                inner.body = nn.TransformerEncoder(layer, self.layers, enable_nested_tensor=False)
                inner.head = nn.Linear(d, len(ALPHABET) + 3)

            def forward(inner, tokens, attributes):
                length = tokens.shape[1]
                context = sum(e(attributes[:, i]) for i, e in enumerate(inner.attribute)) if n_attr else 0
                x = inner.token(tokens) + inner.position(torch.arange(length, device=tokens.device))
                x = x + (context.unsqueeze(1) if n_attr else 0)
                mask = torch.triu(torch.ones(length, length, dtype=torch.bool, device=tokens.device), 1)
                return inner.head(inner.body(x, mask=mask))

        return Model()

    def fit(self, train):
        import torch
        from torch.nn import functional as F

        torch.manual_seed(self.seed)
        self.levels = {a: {v: i + 1 for i, v in enumerate(sorted(train[a].astype(str).unique()))} for a in self.attributes}
        tokens, attributes = self._encode(train["chain"].to_numpy()), self._attributes(train)
        weights = torch.tensor(_normalised_weights(train), dtype=torch.float32)

        # A tenth of the training respondents select the epoch; they never touch the test split.
        rng = np.random.default_rng(self.seed)
        held = rng.random(len(train)) < 0.1
        fit_idx, val_idx = torch.from_numpy(np.flatnonzero(~held)), torch.from_numpy(np.flatnonzero(held))

        self.model = self._build()
        optimiser = torch.optim.AdamW(self.model.parameters(), lr=self.lr, weight_decay=0.01)
        schedule = torch.optim.lr_scheduler.OneCycleLR(
            optimiser, max_lr=self.lr, total_steps=self.epochs * (len(fit_idx) // self.batch_size + 1))

        def loss_of(idx):
            logits = self.model(tokens[idx, :-1], attributes[idx])
            target = tokens[idx, 1:]
            loss = F.cross_entropy(logits.reshape(-1, logits.shape[-1]), target.reshape(-1), ignore_index=0, reduction="none")
            loss = loss.reshape(target.shape).sum(1)
            return (loss * weights[idx]).sum() / weights[idx].sum()

        best, best_state, self.history = float("inf"), None, []
        for _ in range(self.epochs):
            self.model.train()
            order = fit_idx[torch.randperm(len(fit_idx))]
            for start in range(0, len(order), self.batch_size):
                optimiser.zero_grad()
                loss = loss_of(order[start:start + self.batch_size])
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                optimiser.step()
                schedule.step()
            self.model.eval()
            with torch.no_grad():
                validation = float(loss_of(val_idx))
            self.history.append(validation)
            if validation < best:
                best, best_state = validation, {k: v.clone() for k, v in self.model.state_dict().items()}
        self.model.load_state_dict(best_state)
        self.model.eval()
        self.validation_nll = best
        return self

    def sample(self, target, rng):
        import torch

        torch.manual_seed(int(rng.integers(1 << 30)))
        attributes = self._attributes(target)
        tokens = torch.ones((len(target), 1), dtype=torch.long)
        alive = torch.ones(len(target), dtype=torch.bool)
        with torch.no_grad():
            for _ in range(self.max_length + 1):
                logits = self.model(tokens, attributes)[:, -1]
                logits[:, :2] = -float("inf")                      # never pad or begin
                nxt = torch.multinomial(torch.softmax(logits, dim=-1), 1).squeeze(1)
                nxt = torch.where(alive, nxt, torch.zeros_like(nxt))
                tokens = torch.cat([tokens, nxt.unsqueeze(1)], dim=1)
                alive = alive & (nxt != 2)
                if not alive.any():
                    break
        return self._decode(tokens[:, 1:].numpy())


# --------------------------------------------------------------------------- variational autoencoder

class VAEGenerator(_TokenCoding):
    """A conditional variational autoencoder over whole chains.

    An encoder reads a reported chain and gives a distribution over a small latent
    vector; a recurrent decoder writes the chain back from that vector and the
    person's attributes. The prior over the latent vector is itself conditioned on
    the attributes, so that what the attributes say about the day (going out or
    not, for instance) is available when sampling, where no chain is observed.

    Sampling draws the latent vector from that prior and lets the decoder write.
    Like the transformer, the model can write chains no respondent reported. Two
    usual precautions keep the latent vector in use: the weight of the KL term
    rises from zero during the first half of training, and part of the decoder's
    input tokens are hidden so that it cannot rely on the previous activity alone.
    ``validation_kl`` reports how much the latent vector carries, in nats per chain.
    """

    def __init__(self, attributes=ATTRIBUTES, d_model=64, latent=16, max_length=16, epochs=25, batch_size=256,
                 learning_rate=3e-3, token_dropout=0.3, seed=0):
        self.attributes = list(attributes)
        self.d_model, self.latent, self.max_length = d_model, latent, max_length
        self.epochs, self.batch_size, self.lr, self.token_dropout, self.seed = epochs, batch_size, learning_rate, token_dropout, seed

    def _build(self):
        import torch
        from torch import nn

        d, k, n_attr = self.d_model, self.latent, len(self.attributes)
        sizes = [len(self.levels[a]) + 1 for a in self.attributes]
        vocabulary = len(ALPHABET) + 3

        class Model(nn.Module):
            def __init__(inner):
                super().__init__()
                inner.token = nn.Embedding(vocabulary, d, padding_idx=0)
                inner.attribute = nn.ModuleList([nn.Embedding(s, d) for s in sizes])
                inner.encoder = nn.GRU(d, d, batch_first=True, bidirectional=True)
                inner.posterior = nn.Linear(3 * d, 2 * k)
                inner.prior = nn.Sequential(nn.Linear(d, d), nn.Tanh(), nn.Linear(d, 2 * k))
                inner.start = nn.Linear(k + d, d)
                inner.decoder = nn.GRU(2 * d + k, d, batch_first=True)
                inner.head = nn.Linear(d, vocabulary)

            def context(inner, attributes):
                if not n_attr:
                    return torch.zeros(attributes.shape[0], d)
                return sum(e(attributes[:, i]) for i, e in enumerate(inner.attribute))

            def encode(inner, tokens, context):
                lengths = (tokens != 0).sum(1).clamp(min=1)
                packed = nn.utils.rnn.pack_padded_sequence(inner.token(tokens), lengths, batch_first=True, enforce_sorted=False)
                _, hidden = inner.encoder(packed)
                return inner.posterior(torch.cat([hidden[0], hidden[1], context], dim=1)).chunk(2, dim=1)

            def step(inner, embedded, z, context, hidden):
                extra = torch.cat([z, context], dim=1).unsqueeze(1).expand(-1, embedded.shape[1], -1)
                out, hidden = inner.decoder(torch.cat([embedded, extra], dim=2), hidden)
                return inner.head(out), hidden

            def initial(inner, z, context):
                return torch.tanh(inner.start(torch.cat([z, context], dim=1))).unsqueeze(0)

        return Model()

    def fit(self, train):
        import torch
        from torch.nn import functional as F

        torch.manual_seed(self.seed)
        self.levels = {a: {v: i + 1 for i, v in enumerate(sorted(train[a].astype(str).unique()))} for a in self.attributes}
        tokens, attributes = self._encode(train["chain"].to_numpy()), self._attributes(train)
        weights = torch.tensor(_normalised_weights(train), dtype=torch.float32)

        # A tenth of the training respondents select the epoch; they never touch the test split.
        rng = np.random.default_rng(self.seed)
        held = rng.random(len(train)) < 0.1
        fit_idx, val_idx = torch.from_numpy(np.flatnonzero(~held)), torch.from_numpy(np.flatnonzero(held))

        self.model = model = self._build()
        optimiser = torch.optim.AdamW(model.parameters(), lr=self.lr, weight_decay=0.01)
        schedule = torch.optim.lr_scheduler.OneCycleLR(
            optimiser, max_lr=self.lr, total_steps=self.epochs * (len(fit_idx) // self.batch_size + 1))

        def terms(idx, hide):
            """Weighted reconstruction loss and KL divergence, in nats per chain."""
            x, context = tokens[idx], model.context(attributes[idx])
            mean_q, logvar_q = model.encode(x, context)
            mean_p, logvar_p = model.prior(context).chunk(2, dim=1)
            z = mean_q + torch.randn_like(mean_q) * torch.exp(0.5 * logvar_q)
            embedded = model.token(x[:, :-1])
            if hide:
                keep = (torch.rand(embedded.shape[:2]) >= hide).float()
                keep[:, 0] = 1.0                                    # the begin token is always shown
                embedded = embedded * keep.unsqueeze(2)
            logits, _ = model.step(embedded, z, context, model.initial(z, context))
            target = x[:, 1:]
            nll = F.cross_entropy(logits.reshape(-1, logits.shape[-1]), target.reshape(-1), ignore_index=0, reduction="none")
            nll = nll.reshape(target.shape).sum(1)
            kl = 0.5 * (logvar_p - logvar_q + (logvar_q.exp() + (mean_q - mean_p) ** 2) / logvar_p.exp() - 1.0).sum(1)
            w = weights[idx]
            return (nll * w).sum() / w.sum(), (kl * w).sum() / w.sum()

        best, best_state, self.history = float("inf"), None, []
        for epoch in range(self.epochs):
            beta = min(1.0, epoch / max(1.0, self.epochs / 2.0))
            model.train()
            order = fit_idx[torch.randperm(len(fit_idx))]
            for start in range(0, len(order), self.batch_size):
                optimiser.zero_grad()
                nll, kl = terms(order[start:start + self.batch_size], self.token_dropout)
                (nll + beta * kl).backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimiser.step()
                schedule.step()
            model.eval()
            with torch.no_grad():
                torch.manual_seed(self.seed)                         # same noise at every validation pass
                nll, kl = terms(val_idx, 0.0)
                torch.manual_seed(self.seed + epoch + 1)
            bound = float(nll + kl)
            self.history.append(bound)
            if beta >= 1.0 and bound < best:                         # compare epochs on the full bound only
                best, self.validation_kl = bound, float(kl)
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
        model.load_state_dict(best_state)
        model.eval()
        self.validation_bound = best
        return self

    def sample(self, target, rng):
        import torch

        torch.manual_seed(int(rng.integers(1 << 30)))
        model, n = self.model, len(target)
        with torch.no_grad():
            context = model.context(self._attributes(target))
            mean_p, logvar_p = model.prior(context).chunk(2, dim=1)
            z = mean_p + torch.randn_like(mean_p) * torch.exp(0.5 * logvar_p)
            hidden = model.initial(z, context)
            current = torch.ones(n, dtype=torch.long)
            alive = torch.ones(n, dtype=torch.bool)
            written = []
            for _ in range(self.max_length + 1):
                logits, hidden = model.step(model.token(current).unsqueeze(1), z, context, hidden)
                logits = logits[:, 0]
                logits[:, :2] = -float("inf")                      # never pad or begin
                current = torch.multinomial(torch.softmax(logits, dim=-1), 1).squeeze(1)
                current = torch.where(alive, current, torch.zeros_like(current))
                written.append(current)
                alive = alive & (current != 2)
                if not alive.any():
                    break
        return self._decode(torch.stack(written, dim=1).numpy())


# --------------------------------------------------------------------------- adversarial

class GANGenerator(_TokenCoding):
    """A conditional Wasserstein GAN with gradient penalty over whole chains.

    The generator turns a noise vector and the person's attributes into one
    distribution over activities for every position of the chain, all at once;
    a critic sees either such an output or a reported chain, with the same
    attributes, and learns to tell them apart. There is no likelihood, so the
    number of training steps is fixed in advance instead of being selected on
    held-out respondents. Training batches are drawn in proportion to the
    survey weights. The chain is read off as the most likely activity at each
    position, up to the first end mark.

    This is the family Shone and Hillel compare with their autoencoders.
    """

    def __init__(self, attributes=ATTRIBUTES, d_model=64, hidden=256, noise=32, max_length=16, steps=2500,
                 critic_steps=5, batch_size=256, learning_rate=1e-4, penalty=10.0, seed=0):
        self.attributes = list(attributes)
        self.d_model, self.hidden, self.noise, self.max_length = d_model, hidden, noise, max_length
        self.steps, self.critic_steps, self.batch_size = steps, critic_steps, batch_size
        self.lr, self.penalty, self.seed = learning_rate, penalty, seed

    # positions hold: 0 pad, 1 end, 2.. activities (the begin mark is not generated)
    def _one_hot(self, chains):
        import torch
        tokens = self._encode(chains)[:, 1:]
        tokens = torch.where(tokens > 0, tokens - 1, tokens)
        return torch.nn.functional.one_hot(tokens, len(ALPHABET) + 2).float()

    def _build(self):
        import torch
        from torch import nn

        d, n_attr, hidden = self.d_model, len(self.attributes), self.hidden
        sizes = [len(self.levels[a]) + 1 for a in self.attributes]
        length, vocabulary = self.max_length + 1, len(ALPHABET) + 2

        class Context(nn.Module):
            def __init__(inner):
                super().__init__()
                inner.attribute = nn.ModuleList([nn.Embedding(s, d) for s in sizes])

            def forward(inner, attributes):
                if not n_attr:
                    return torch.zeros(attributes.shape[0], d)
                return sum(e(attributes[:, i]) for i, e in enumerate(inner.attribute))

        class Generator(nn.Module):
            def __init__(inner):
                super().__init__()
                inner.context = Context()
                inner.body = nn.Sequential(nn.Linear(self.noise + d, hidden), nn.ReLU(), nn.Linear(hidden, hidden), nn.ReLU(),
                                           nn.Linear(hidden, length * vocabulary))

            def forward(inner, z, attributes):
                logits = inner.body(torch.cat([z, inner.context(attributes)], dim=1))
                return torch.softmax(logits.reshape(-1, length, vocabulary), dim=2)

        class Critic(nn.Module):
            def __init__(inner):
                super().__init__()
                inner.context = Context()
                inner.body = nn.Sequential(nn.Linear(length * vocabulary + d, hidden), nn.LeakyReLU(0.2),
                                           nn.Linear(hidden, hidden), nn.LeakyReLU(0.2), nn.Linear(hidden, 1))

            def forward(inner, x, attributes):
                return inner.body(torch.cat([x.reshape(x.shape[0], -1), inner.context(attributes)], dim=1)).squeeze(1)

        return Generator(), Critic()

    def fit(self, train):
        import torch

        torch.manual_seed(self.seed)
        self.levels = {a: {v: i + 1 for i, v in enumerate(sorted(train[a].astype(str).unique()))} for a in self.attributes}
        real, attributes = self._one_hot(train["chain"].to_numpy()), self._attributes(train)
        weights = torch.tensor(_normalised_weights(train), dtype=torch.float32)

        self.generator, critic = self._build()
        opt_g = torch.optim.Adam(self.generator.parameters(), lr=self.lr, betas=(0.5, 0.9))
        opt_c = torch.optim.Adam(critic.parameters(), lr=self.lr, betas=(0.5, 0.9))

        def batch():
            idx = torch.multinomial(weights, self.batch_size, replacement=True)
            return real[idx], attributes[idx]

        self.history = []
        for _ in range(self.steps):
            for _ in range(self.critic_steps):
                x, a = batch()
                with torch.no_grad():
                    fake = self.generator(torch.randn(len(x), self.noise), a)
                mix = torch.rand(len(x), 1, 1)
                between = (mix * x + (1 - mix) * fake).requires_grad_(True)
                gradient = torch.autograd.grad(critic(between, a).sum(), between, create_graph=True)[0]
                slope = gradient.reshape(len(x), -1).norm(dim=1)
                distance = critic(x, a).mean() - critic(fake, a).mean()
                loss = -distance + self.penalty * ((slope - 1) ** 2).mean()
                opt_c.zero_grad()
                loss.backward()
                opt_c.step()
            x, a = batch()
            loss = -critic(self.generator(torch.randn(len(x), self.noise), a), a).mean()
            opt_g.zero_grad()
            loss.backward()
            opt_g.step()
            self.history.append(float(distance.detach()))
        self.generator.eval()
        self.critic_distance = float(np.mean(self.history[-100:]))      # what the critic still sees, at the end
        return self

    def sample(self, target, rng):
        import torch

        torch.manual_seed(int(rng.integers(1 << 30)))
        with torch.no_grad():
            tokens = self.generator(torch.randn(len(target), self.noise), self._attributes(target)).argmax(dim=2).numpy()
        letters = np.array(list("??" + ALPHABET))
        out = []
        for row in tokens:
            ends = np.flatnonzero(row <= 1)                         # the chain stops at the first end mark or pad
            row = row[:ends[0]] if len(ends) else row
            chain = "".join(letters[row])
            out.append(chain if chain else "h")
        return np.array(out, dtype=object)
