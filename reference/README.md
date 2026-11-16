# Reference tables

`epci_loire_atlantique.csv`: the intercommunalité (EPCI) of each of the 207
communes of Loire-Atlantique, as returned on 13 November 2026 by the national
geography API:

    https://geo.api.gouv.fr/departements/44/communes?fields=nom,code,codeEpci
    https://geo.api.gouv.fr/epcis?fields=nom,code

Redon Agglomération is counted for its eight Loire-Atlantique communes only;
the rest of it lies in Ille-et-Vilaine and Morbihan.

`communes_2015_to_2026.csv`: the twenty communes of the 2015 regional survey
(EDGT Loire-Atlantique) that have since merged into a new commune, with the
commune they belong to today. Eighteen come from the national geography API
(`/communes_associees_deleguees`, field `chefLieu`); Saint-Géréon and Le
Fresne-sur-Loire have no delegated commune and were matched to the current
communes that carry their names (Ancenis-Saint-Géréon, Ingrandes-le-Fresne-sur-Loire).
