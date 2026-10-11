"""
Baut vier Formalisierungs-Varianten fuer den symmetrischen
Granularitaetsvergleich EQF <-> DQR:

  data/formalized/eqf_1D.ttl   8  Niveaus (eqf:Level1..8)
  data/formalized/eqf_2D.ttl   32 = 8 Niveaus + 24 Dimensionsfacetten
                                    (eqf:L{n}_Knowledge / _Skills / _ResponsibilityAutonomy)
  data/formalized/dqr_1D.ttl   8  Niveaus (dqr:L1..8)
  data/formalized/dqr_2D.ttl   40 = 8 Niveaus + 32 Dimensionsfacetten
                                    (dqr:L{n}_Knowledge / _Skills / _SocialCompetence / _Autonomy)

Einheitliche Konventionen (Nutzerentscheidung 2026-09-05,
Namespace-Revision 2026-09-06):
  * EQF-URI-Basis autoritativ: eqf: = http://data.europa.eu/snb/eqf/ .
  * DQR-URI-Basis harmonisiert: harm-dqr: = http://hr-qde.org/harmonised/source/dqr/ .
    Jeder DQR-Konzeptknoten traegt owl:sameAs auf die originale
    data.bmbf.de-URI (Bruecke fuer externe Referenzen). Der DQR<->EQF-
    Crosswalk und die EQF-seitige Niveaukalibrierung zeigen auf die
    harm-dqr:-Anker.
  * harm:derivedFrom harm:kqr_eqf bzw. harm:kqr_dqr (IRI, in
    hrqde-harmonisation-schema.ttl deklariert -- nicht neu praegen).
  * harm:sourceIdentifier "<lokaler Name>", a harm:LevelConcept
    auf allen Konzepten (EQF- und DQR-Konzepte sind Qualifikationsniveaus).
  * Der DQR<->EQF-Crosswalk steht auf der DQR-Seite:
      harm-dqr:L{n}            skos:exactMatch  eqf:Level{n}
      harm-dqr:L{n}_Knowledge  skos:exactMatch  eqf:L{n}_Knowledge
      harm-dqr:L{n}_Skills     skos:exactMatch  eqf:L{n}_Skills
      harm-dqr:L{n}_SocialCompetence skos:narrowMatch eqf:L{n}_ResponsibilityAutonomy
      harm-dqr:L{n}_Autonomy         skos:narrowMatch eqf:L{n}_ResponsibilityAutonomy
    (Praedikate = eval/G_struct.json, German EQF Referencing Report 2012/2013.)
    EQF-Dateien bleiben ausgehend mapping-frei (reiner Referenzrahmen).

Quellen:
  * EQF-Deskriptoren EN: OJ C 189, 15.6.2017, Annex II (Recommendation 2017/C 189/03).
  * EQF-Deskriptoren DE: Europass, "Beschreibung der acht EQR-Niveaus"
    (https://europass.europa.eu/de/description-eight-eqf-levels) = amtliche
    EQR-Deskriptoren Anhang II.
  * DQR-Niveauindikatoren DE: data/formalized/dqr_3.ttl (amtliche DQR-Matrix).
  * DQR-Dimensionsdeskriptoren DE: data/formalized/dqr_levelProposal.ttl
    (verifiziert gegen https://www.dqr.de, Niveau-Detailseiten 1-8).

Reine Datenpflege -- kein Klassifikationslauf, keine Aenderung an
dqr_3.ttl / dqr_levelProposal.ttl / eqf_2017.ttl.
"""

from __future__ import annotations

import argparse
from pathlib import Path

FORMALIZED = Path(__file__).resolve().parents[1] / "data" / "formalized"

EQF = "http://data.europa.eu/snb/eqf/"
DQR = "http://hr-qde.org/harmonised/source/dqr/"
DQR_AUTHORITY = "http://data.bmbf.de/dqr/"  # owl:sameAs-Bruecke je Konzept
DASH = "–"  # en dash, wie in eqf_2017.ttl / dqr_levelProposal.ttl

PREFIXES = [
    ("eqf", EQF),
    ("harm-dqr", DQR),
    ("harm", "http://hr-qde.org/harmonised/"),
    ("skos", "http://www.w3.org/2004/02/skos/core#"),
    ("owl", "http://www.w3.org/2002/07/owl#"),
    ("dct", "http://purl.org/dc/terms/"),
    ("xsd", "http://www.w3.org/2001/XMLSchema#"),
]

# =============================================================================
# EQF -- amtliche Deskriptoren
# =============================================================================

EQF_KNOWLEDGE_DE = {
    1: "grundlegendes Allgemeinwissen",
    2: "grundlegendes Faktenwissen in einem Arbeits- oder Lernbereich",
    3: "Kenntnisse von Fakten, Grundsätzen, Verfahren und allgemeinen Begriffen in einem Arbeits- oder Lernbereich",
    4: "breites Spektrum an Fakten- und Theoriewissen in einem Arbeits- oder Lernbereich",
    5: "umfassendes, spezialisiertes Fakten- und Theoriewissen in einem Arbeits- oder Lernbereich sowie Bewusstsein für die Grenzen dieser Kenntnisse",
    6: "fortgeschrittene Kenntnisse in einem Arbeits- oder Lernbereich unter Einsatz eines kritischen Verständnisses von Theorien und Grundsätzen",
    7: "hoch spezialisierte Kenntnisse, die zum Teil an neueste Erkenntnisse in einem Arbeits- oder Lernbereich anknüpfen, als Grundlage für innovative Denkansätze und/oder Forschung; kritisches Bewusstsein für Wissensfragen in einem Bereich und an der Schnittstelle zwischen verschiedenen Bereichen",
    8: "Spitzenkenntnisse in einem Arbeits- oder Lernbereich und an der Schnittstelle zwischen verschiedenen Bereichen",
}
EQF_SKILLS_DE = {
    1: "grundlegende Fertigkeiten, die zur Erledigung einfacher Aufgaben erforderlich sind",
    2: "grundlegende kognitive und praktische Fertigkeiten, die zur Nutzung einschlägiger Informationen erforderlich sind, um Aufgaben zu erledigen und Routineprobleme unter Verwendung einfacher Regeln und Werkzeuge zu lösen",
    3: "eine Reihe kognitiver und praktischer Fertigkeiten zur Erledigung von Aufgaben und zur Lösung von Problemen, wobei grundlegende Methoden, Werkzeuge, Materialien und Informationen ausgewählt und angewandt werden",
    4: "eine Reihe kognitiver und praktischer Fertigkeiten, die erforderlich sind, um Lösungen für spezielle Probleme in einem Arbeits- oder Lernbereich zu finden",
    5: "umfassende kognitive und praktische Fertigkeiten, die erforderlich sind, um kreative Lösungen für abstrakte Probleme zu erarbeiten",
    6: "fortgeschrittene Fertigkeiten, die die Beherrschung des Faches sowie Innovationsfähigkeit erkennen lassen und zur Lösung komplexer und unvorhersehbarer Probleme in einem spezialisierten Arbeits- oder Lernbereich nötig sind",
    7: "spezialisierte Problemlösungsfertigkeiten im Bereich Forschung und/oder Innovation, um neue Kenntnisse zu gewinnen und neue Verfahren zu entwickeln sowie um Wissen aus verschiedenen Bereichen zu integrieren",
    8: "im höchsten Maße fortgeschrittene und spezialisierte Fertigkeiten und Methoden, einschließlich Synthese und Evaluierung, zur Lösung zentraler Problemstellungen in den Bereichen Forschung und/oder Innovation und zur Erweiterung oder Neudefinition vorhandener Kenntnisse oder beruflicher Praxis",
}
EQF_RESP_DE = {
    1: "Arbeiten oder Lernen unter direkter Anleitung in einem strukturierten Kontext",
    2: "Arbeiten oder Lernen unter Anleitung mit einem gewissen Maß an Selbstständigkeit",
    3: "Verantwortung für die Erledigung von Arbeits- oder Lernaufgaben übernehmen; bei der Lösung von Problemen das eigene Verhalten an die jeweiligen Umstände anpassen",
    4: "selbstständiges Tätigwerden innerhalb der Handlungsparameter von Arbeits- oder Lernkontexten, die in der Regel bekannt sind, sich jedoch ändern können; Beaufsichtigung der Routinearbeit anderer Personen, wobei ein gewisses Maß an Verantwortung für die Bewertung und Verbesserung der Arbeits- oder Lernaktivitäten übernommen wird",
    5: "Leiten und Beaufsichtigen in Arbeits- oder Lernkontexten, in denen unvorhersehbare Änderungen auftreten; Überprüfung und Entwicklung der eigenen Leistung und der Leistung anderer Personen",
    6: "Leitung komplexer fachlicher oder beruflicher Tätigkeiten oder Projekte und Übernahme von Entscheidungsverantwortung in unvorhersehbaren Arbeits- oder Lernkontexten; Übernahme von Verantwortung für die berufliche Entwicklung von Einzelpersonen und Gruppen",
    7: "Leitung und Gestaltung komplexer, unvorhersehbarer Arbeits- oder Lernkontexte, die neue strategische Ansätze erfordern; Übernahme von Verantwortung für Beiträge zum Fachwissen und zur Berufspraxis und/oder für die Überprüfung der strategischen Leistung von Teams",
    8: "fachliche Autorität, Innovationsfähigkeit, Selbstständigkeit, wissenschaftliche und berufliche Integrität und nachhaltiges Engagement bei der Entwicklung neuer Ideen oder Verfahren in führenden Arbeits- oder Lernkontexten, einschließlich der Forschung",
}

EQF_KNOWLEDGE_EN = {
    1: "basic general knowledge",
    2: "basic factual knowledge of a field of work or study",
    3: "knowledge of facts, principles, processes and general concepts, in a field of work or study",
    4: "factual and theoretical knowledge in broad contexts within a field of work or study",
    5: "comprehensive, specialised, factual and theoretical knowledge within a field of work or study and an awareness of the boundaries of that knowledge",
    6: "advanced knowledge of a field of work or study, involving a critical understanding of theories and principles",
    7: "highly specialised knowledge, some of which is at the forefront of knowledge in a field of work or study, as the basis for original thinking and/or research; critical awareness of knowledge issues in a field and at the interface between different fields",
    8: "knowledge at the most advanced frontier of a field of work or study and at the interface between fields",
}
EQF_SKILLS_EN = {
    1: "basic skills required to carry out simple tasks",
    2: "basic cognitive and practical skills required to use relevant information in order to carry out tasks and to solve routine problems using simple rules and tools",
    3: "a range of cognitive and practical skills required to accomplish tasks and solve problems by selecting and applying basic methods, tools, materials and information",
    4: "a range of cognitive and practical skills required to generate solutions to specific problems in a field of work or study",
    5: "a comprehensive range of cognitive and practical skills required to develop creative solutions to abstract problems",
    6: "advanced skills, demonstrating mastery and innovation, required to solve complex and unpredictable problems in a specialised field of work or study",
    7: "specialised problem-solving skills required in research and/or innovation in order to develop new knowledge and procedures and to integrate knowledge from different fields",
    8: "the most advanced and specialised skills and techniques, including synthesis and evaluation, required to solve critical problems in research and/or innovation and to extend and redefine existing knowledge or professional practice",
}
EQF_RESP_EN = {
    1: "work or study under direct supervision in a structured context",
    2: "work or study under supervision with some autonomy",
    3: "take responsibility for completion of tasks in work or study; adapt own behaviour to circumstances in solving problems",
    4: "exercise self-management within the guidelines of work or study contexts that are usually predictable, but are subject to change; supervise the routine work of others, taking some responsibility for the evaluation and improvement of work or study activities",
    5: "exercise management and supervision in contexts of work or study activities where there is unpredictable change; review and develop performance of self and others",
    6: "manage complex technical or professional activities or projects, taking responsibility for decision-making in unpredictable work or study contexts; take responsibility for managing professional development of individuals and groups",
    7: "manage and transform work or study contexts that are complex, unpredictable and require new strategic approaches; take responsibility for contributing to professional knowledge and practice and/or for reviewing the strategic performance of teams",
    8: "demonstrate substantial authority, innovation, autonomy, scholarly and professional integrity and sustained commitment to the development of new ideas or processes at the forefront of work or study contexts including research",
}

EQF_SCOPE_EN = {
    5: "The descriptor for the short cycle (Bologna process) corresponds to EQF Level 5.",
    6: "The descriptor for the first cycle (Bologna process) corresponds to EQF Level 6.",
    7: "The descriptor for the second cycle (Bologna process) corresponds to EQF Level 7.",
    8: "The descriptor for the third cycle (Bologna process) corresponds to EQF Level 8.",
}

# (localsuffix, descriptorType, de-Dimensionsname, en-Dimensionsname, DE-map, EN-map)
EQF_DIMS = [
    ("Knowledge", "knowledge", "Kenntnisse", "Knowledge", EQF_KNOWLEDGE_DE, EQF_KNOWLEDGE_EN),
    ("Skills", "skills", "Fertigkeiten", "Skills", EQF_SKILLS_DE, EQF_SKILLS_EN),
    ("ResponsibilityAutonomy", "responsibility_autonomy",
     "Verantwortung und Selbstständigkeit", "Responsibility and Autonomy",
     EQF_RESP_DE, EQF_RESP_EN),
]


def eqf_level_def_en(n: int) -> str:
    return (f"Knowledge: {EQF_KNOWLEDGE_EN[n]}. "
            f"Skills: {EQF_SKILLS_EN[n]}. "
            f"Responsibility and autonomy: {EQF_RESP_EN[n]}.")


def eqf_level_def_de(n: int) -> str:
    return (f"Kenntnisse: {EQF_KNOWLEDGE_DE[n]}. "
            f"Fertigkeiten: {EQF_SKILLS_DE[n]}. "
            f"Verantwortung und Selbstständigkeit: {EQF_RESP_DE[n]}.")


# =============================================================================
# DQR -- Niveauindikatoren (dqr_3.ttl) und Dimensionsdeskriptoren
# (dqr_levelProposal.ttl)
# =============================================================================

DQR_LEVEL_DEF_DE = {
    1: "Kompetenzen zur Erfüllung einfacher Anforderungen in einem überschaubaren und stabil strukturierten Lern- oder Arbeitsbereich. Die Erfüllung der Aufgaben erfolgt unter Anleitung.",
    2: "Kompetenzen zur fachgerechten Erfüllung grundlegender Anforderungen in einem überschaubaren und stabil strukturierten Lern- oder Arbeitsbereich. Die Erfüllung der Aufgaben erfolgt weitgehend selbstständig unter Anleitung.",
    3: "Kompetenzen zur selbstständigen Erfüllung fachlicher Anforderungen in einem noch überschaubaren und zum Teil offen strukturierten Lernbereich oder beruflichen Tätigkeitsfeld.",
    4: "Kompetenzen zur selbstständigen Planung und Bearbeitung fachlicher Aufgabenstellungen in einem umfassenden, sich verändernden Lernbereich oder beruflichen Tätigkeitsfeld.",
    5: "Kompetenzen zur selbstständigen Planung und Bearbeitung umfassender fachlicher Aufgabenstellungen in einem komplexen, spezialisierten, sich verändernden Lernbereich oder beruflichen Tätigkeitsfeld.",
    6: "Kompetenzen zur Planung, Bearbeitung und Auswertung von umfassenden fachlichen Aufgaben- und Problemstellungen sowie zur eigenverantwortlichen Steuerung von Prozessen in Teilbereichen eines wissenschaftlichen Faches oder in einem beruflichen Tätigkeitsfeld.",
    7: "Kompetenzen zur Bearbeitung neuer komplexer Aufgaben- und Problemstellungen sowie zur eigenverantwortlichen Steuerung von Prozessen in einem wissenschaftlichen Fach oder in einem strategieorientierten beruflichen Tätigkeitsfeld.",
    8: "Kompetenzen zur Gewinnung von Forschungserkenntnissen in einem wissenschaftlichen Fach oder zur Entwicklung innovativer Lösungen und Verfahren in einem beruflichen Tätigkeitsfeld.",
}

DQR_KNOWLEDGE_DE = {
    1: "Über elementares allgemeines Wissen verfügen; einen ersten Einblick in einen Lern- oder Arbeitsbereich haben.",
    2: "Über grundlegendes allgemeines Wissen und grundlegendes Fachwissen in einem Lern- oder Arbeitsbereich verfügen.",
    3: "Über erweitertes allgemeines Wissen oder über erweitertes Fachwissen in einem Lernbereich oder beruflichen Tätigkeitsfeld verfügen.",
    4: "Über vertieftes allgemeines Wissen oder über fachtheoretisches Wissen in einem Lernbereich oder beruflichen Tätigkeitsfeld verfügen.",
    5: "Über integriertes Fachwissen in einem Lernbereich oder über integriertes berufliches Wissen in einem Tätigkeitsfeld verfügen. Das schließt auch vertieftes fachtheoretisches Wissen ein. Umfang und Grenzen des Lernbereichs oder beruflichen Tätigkeitsfelds kennen.",
    6: "Über breites und integriertes Wissen einschließlich der wissenschaftlichen Grundlagen, der praktischen Anwendung eines wissenschaftlichen Faches sowie eines kritischen Verständnisses der wichtigsten Theorien und Methoden entsprechend der Bachelor-Ebene des Qualifikationsrahmens für Deutsche Hochschulabschlüsse oder über breites und integriertes berufliches Wissen einschließlich der aktuellen fachlichen Entwicklungen verfügen. Kenntnisse zur Weiterentwicklung eines wissenschaftlichen Faches oder eines beruflichen Tätigkeitsfeldes besitzen. Über einschlägiges Wissen an Schnittstellen zu anderen Bereichen verfügen.",
    7: "Über umfassendes, detailliertes und spezialisiertes Wissen auf dem neuesten Erkenntnisstand in einem wissenschaftlichen Fach entsprechend der Master-Ebene des Qualifikationsrahmens für Deutsche Hochschulabschlüsse oder über umfassendes berufliches Wissen in einem strategieorientierten beruflichen Tätigkeitsfeld verfügen. Über erweitertes Wissen in angrenzenden Bereichen verfügen.",
    8: "Über umfassendes, spezialisiertes und systematisches Wissen in einer Forschungsdisziplin verfügen und zur Erweiterung des Wissens der Fachdisziplin beitragen, entsprechend der Doktoratsebene des Qualifikationsrahmens für Deutsche Hochschulabschlüsse, oder über umfassendes berufliches Wissen in einem strategie- und innovationsorientierten beruflichen Tätigkeitsfeld verfügen. Über entsprechendes Wissen an den Schnittstellen zu angrenzenden Bereichen verfügen.",
}
DQR_SKILLS_DE = {
    1: "Über kognitive und praktische Fertigkeiten verfügen, um einfache Aufgaben nach vorgegebenen Regeln auszuführen und deren Ergebnisse zu beurteilen; elementare Zusammenhänge herstellen.",
    2: "Über grundlegende kognitive und praktische Fertigkeiten zur Ausführung von Aufgaben in einem Lern- oder Arbeitsbereich verfügen und deren Ergebnisse nach vorgegebenen Maßstäben beurteilen sowie Zusammenhänge herstellen.",
    3: "Über ein Spektrum von kognitiven und praktischen Fertigkeiten zur Planung und Bearbeitung von fachlichen Aufgaben in einem Lernbereich oder beruflichen Tätigkeitsfeld verfügen. Ergebnisse nach weitgehend vorgegebenen Maßstäben beurteilen und einfache Transferleistungen erbringen.",
    4: "Über ein breites Spektrum kognitiver und praktischer Fertigkeiten verfügen, die selbständige Aufgabenbearbeitung und Problemlösung sowie die Beurteilung von Arbeitsergebnissen und -prozessen unter Einbeziehung von Handlungsalternativen und Wechselwirkungen mit benachbarten Bereichen ermöglichen. Transferleistungen erbringen.",
    5: "Über ein sehr breites Spektrum spezialisierter kognitiver und praktischer Fertigkeiten verfügen. Arbeitsprozesse übergreifend planen und sie unter umfassender Einbeziehung von Handlungsalternativen und Wechselwirkungen mit benachbarten Bereichen beurteilen. Umfassende Transferleistungen erbringen.",
    6: "Über ein sehr breites Spektrum an Methoden zur Bearbeitung komplexer Probleme in einem wissenschaftlichen Fach entsprechend der Bachelor-Ebene des Qualifikationsrahmens für Deutsche Hochschulabschlüsse, weiteren Lernbereichen oder einem beruflichen Tätigkeitsfeld verfügen. Neue Lösungen erarbeiten und unter Berücksichtigung unterschiedlicher Maßstäbe beurteilen, auch bei sich häufig ändernden Anforderungen.",
    7: "Über spezialisierte fachliche oder konzeptionelle Fertigkeiten zur Lösung auch strategischer Probleme in einem wissenschaftlichen Fach entsprechend der Master-Ebene des Qualifikationsrahmens für Deutsche Hochschulabschlüsse oder in einem beruflichen Tätigkeitsfeld verfügen. Auch bei unvollständiger Information Alternativen abwägen. Neue Ideen oder Verfahren entwickeln, anwenden und unter Berücksichtigung unterschiedlicher Beurteilungsmaßstäbe bewerten.",
    8: "Über umfassend entwickelte Fertigkeiten zur Identifizierung und Lösung neuartiger Problemstellungen in Forschung, Entwicklung oder Innovation in einem spezialisierten wissenschaftlichen Fach entsprechend der Doktoratsebene oder in einem beruflichen Tätigkeitsfeld verfügen. Innovative Prozesse auch tätigkeitsfeldübergreifend konzipieren, durchführen, steuern, reflektieren und beurteilen. Neue Ideen und Verfahren beurteilen.",
}
DQR_SOCIAL_DE = {
    1: "Mit anderen zusammen lernen oder arbeiten, sich mündlich und schriftlich informieren und austauschen.",
    2: "In einer Gruppe mitwirken, allgemeine Anregungen und Kritik aufnehmen und äußern sowie in mündlicher und schriftlicher Kommunikation situationsgerecht agieren und reagieren.",
    3: "In einer Gruppe mitwirken und punktuell Unterstützung anbieten, die Lern- oder Arbeitsumgebung mitgestalten, Abläufe gestalten und Ergebnisse adressatenbezogen darstellen.",
    4: "Die Arbeit in einer Gruppe und deren Lern- oder Arbeitsumgebung mitgestalten und kontinuierlich Unterstützung anbieten, Abläufe und Ergebnisse begründen sowie über Sachverhalte umfassend kommunizieren.",
    5: "Arbeitsprozesse kooperativ, auch in heterogenen Gruppen, planen und gestalten, andere anleiten und mit fundierter Lernberatung unterstützen. Auch fachübergreifend komplexe Sachverhalte strukturiert, zielgerichtet und adressatenbezogen darstellen. Interessen und Bedarf von Adressaten vorausschauend berücksichtigen.",
    6: "In Expertenteams verantwortlich arbeiten oder Gruppen oder Organisationen verantwortlich leiten. Die fachliche Entwicklung anderer anleiten und vorausschauend mit Problemen im Team umgehen. Komplexe fachbezogene Probleme und Lösungen gegenüber Fachleuten argumentativ vertreten und mit ihnen weiterentwickeln.",
    7: "Gruppen oder Organisationen im Rahmen komplexer Aufgabenstellungen verantwortlich leiten und ihre Arbeitsergebnisse vertreten. Die fachliche Entwicklung anderer gezielt fördern. Bereichsspezifische und bereichsübergreifende Diskussionen führen.",
    8: "Organisationen oder Gruppen mit komplexen beziehungsweise interdisziplinären Aufgabenstellungen verantwortlich leiten und dabei ihre Potenziale aktivieren. Die fachliche Entwicklung anderer nachhaltig und gezielt fördern. Fachübergreifend Diskussionen führen und in fachspezifischen Diskussionen innovative Beiträge einbringen, auch in internationalen Kontexten.",
}
DQR_AUTONOMY_DE = {
    1: "Unter Anleitung lernen oder arbeiten; das eigene und das Handeln anderer einschätzen und Lernberatung annehmen.",
    2: "In bekannten und stabilen Kontexten weitgehend unter Anleitung verantwortungsbewusst lernen oder arbeiten, das eigene und das Handeln anderer einschätzen sowie vorgegebene Lernhilfen nutzen und Lernberatung nachfragen.",
    3: "Auch in weniger bekannten Kontexten eigenständig und verantwortungsbewusst lernen oder arbeiten, das eigene und das Handeln anderer einschätzen sowie Lernberatung nachfragen und verschiedene Lernhilfen auswählen.",
    4: "Sich Lern- und Arbeitsziele setzen, sie reflektieren, realisieren und verantworten.",
    5: "Eigene und fremd gesetzte Lern- und Arbeitsziele reflektieren, bewerten, selbstgesteuert verfolgen und verantworten sowie Konsequenzen für die Arbeitsprozesse im Team ziehen.",
    6: "Ziele für Lern- und Arbeitsprozesse definieren, reflektieren und bewerten und Lern- und Arbeitsprozesse eigenständig und nachhaltig gestalten.",
    7: "Für neue anwendungs- oder forschungsorientierte Aufgaben Ziele unter Reflexion der möglichen gesellschaftlichen, wirtschaftlichen und kulturellen Auswirkungen definieren, geeignete Mittel einsetzen und hierfür Wissen eigenständig erschließen.",
    8: "Für neue komplexe anwendungs- oder forschungsorientierte Aufgaben Ziele unter Reflexion der möglichen gesellschaftlichen, wirtschaftlichen und kulturellen Auswirkungen definieren, geeignete Mittel wählen und neue Ideen und Prozesse entwickeln.",
}

DQR_SOCIAL_SCOPE_DE = "Organisationen umfassen Unternehmen, Verwaltungseinheiten oder gemeinnützige Organisationen."

# (localsuffix, descriptorType, de-Praefix, en-Praefix, DE-map, eqf-Zielsuffix, Praedikat)
DQR_DIMS = [
    ("Knowledge", "knowledge", "Wissen", "Knowledge", DQR_KNOWLEDGE_DE, "Knowledge", "exactMatch"),
    ("Skills", "skills", "Fertigkeiten", "Skills", DQR_SKILLS_DE, "Skills", "exactMatch"),
    ("SocialCompetence", "social_competence", "Sozialkompetenz", "Social Competence",
     DQR_SOCIAL_DE, "ResponsibilityAutonomy", "narrowMatch"),
    ("Autonomy", "autonomy", "Selbstständigkeit", "Autonomy",
     DQR_AUTONOMY_DE, "ResponsibilityAutonomy", "narrowMatch"),
]


# =============================================================================
# Turtle-Writer
# =============================================================================

def _lit(value: str, lang: str | None = None) -> str:
    assert '"' not in value and "\n" not in value, value
    return f'"{value}"' + (f"@{lang}" if lang else "")


def _block(subject: str, triples: list[tuple[str, str]]) -> str:
    body = " ;\n    ".join(f"{p} {o}" for p, o in triples)
    return f"{subject} {body} ."


def _header(title_lines: list[str]) -> str:
    lines = ["# " + "=" * 76]
    lines += [f"# {ln}" if ln else "#" for ln in title_lines]
    lines += ["# " + "=" * 76, ""]
    lines += [f"@prefix {p}: <{u}> ." for p, u in PREFIXES]
    lines += [""]
    return "\n".join(lines)


def _eqf_scheme() -> str:
    return _block("eqf:EQFScheme", [
        ("a", "skos:ConceptScheme"),
        ("skos:prefLabel", f'{_lit("European Qualifications Framework", "en")} , {_lit("Europäischer Qualifikationsrahmen", "de")}'),
        ("skos:definition", _lit(
            "The EQF relates countries' qualifications systems to a common European "
            "reference framework. It has eight levels defined by learning outcomes across "
            "three dimensions: knowledge, skills, and responsibility and autonomy.", "en")),
        ("dct:source", "<https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:C:2017:189:TOC>"),
        ("skos:hasTopConcept", " , ".join(f"eqf:Level{n}" for n in range(1, 9))),
    ])


def _dqr_scheme() -> str:
    return _block("harm-dqr:DQRScheme", [
        ("a", "skos:ConceptScheme"),
        ("skos:prefLabel", f'{_lit("Deutscher Qualifikationsrahmen für lebenslanges Lernen", "de")} , {_lit("German Qualifications Framework for Lifelong Learning", "en")}'),
        ("skos:hasTopConcept", " , ".join(f"harm-dqr:L{n}" for n in range(1, 9))),
    ])


def _eqf_level_block(n: int, *, with_dim_links: bool) -> str:
    triples: list[tuple[str, str]] = [
        ("a", "skos:Concept"),
        ("skos:inScheme", "eqf:EQFScheme"),
        ("skos:prefLabel", f'{_lit(f"EQF Level {n}", "en")} , {_lit(f"EQR-Niveau {n}", "de")}'),
        ("skos:definition", f'{_lit(eqf_level_def_en(n), "en")} , {_lit(eqf_level_def_de(n), "de")}'),
    ]
    if n in EQF_SCOPE_EN:
        triples.append(("skos:scopeNote", _lit(EQF_SCOPE_EN[n], "en")))
    if n > 1:
        triples.append(("skos:broader", f"eqf:Level{n - 1}"))
    if with_dim_links:
        for suf, *_ in EQF_DIMS:
            triples.append((f"skos:narrower", f"eqf:L{n}_{suf}"))
    triples += [
        ("eqf:levelNumber", f'"{n}"^^xsd:integer'),
        ("harm:derivedFrom", "harm:kqr_eqf"),
        ("harm:sourceIdentifier", _lit(f"Level{n}")),
        ("a", "harm:LevelConcept"),
        ("skos:exactMatch", f"harm-dqr:L{n}"),
    ]
    return _block(f"eqf:Level{n}", triples)


def _eqf_facet_block(n: int, dim) -> str:
    suf, dtype, de_dim, en_dim, de_map, en_map = dim
    return _block(f"eqf:L{n}_{suf}", [
        ("a", "skos:Concept"),
        ("skos:inScheme", "eqf:EQFScheme"),
        ("skos:broader", f"eqf:Level{n}"),
        ("skos:prefLabel", f'{_lit(f"{en_dim} {DASH} EQF Level {n}", "en")} , {_lit(f"{de_dim} {DASH} EQR-Niveau {n}", "de")}'),
        ("skos:definition", f'{_lit(en_map[n], "en")} , {_lit(de_map[n], "de")}'),
        ("eqf:descriptorType", _lit(dtype)),
        ("harm:derivedFrom", "harm:kqr_eqf"),
        ("harm:sourceIdentifier", _lit(f"L{n}_{suf}")),
        ("a", "harm:LevelConcept"),
    ])


def _dqr_level_block(n: int, *, with_dim_links: bool) -> str:
    triples: list[tuple[str, str]] = [
        ("a", "skos:Concept"),
        ("owl:sameAs", f"<{DQR_AUTHORITY}L{n}>"),
        ("skos:inScheme", "harm-dqr:DQRScheme"),
        ("skos:prefLabel", f'{_lit(f"DQR-Niveau {n}", "de")} , {_lit(f"DQR Level {n}", "en")}'),
        ("skos:definition", _lit(DQR_LEVEL_DEF_DE[n], "de")),
    ]
    if n > 1:
        triples.append(("skos:broader", f"harm-dqr:L{n - 1}"))
    if with_dim_links:
        for suf, *_ in DQR_DIMS:
            triples.append(("skos:narrower", f"harm-dqr:L{n}_{suf}"))
    triples += [
        ("harm-dqr:levelNumber", f'"{n}"^^xsd:integer'),
        ("harm:derivedFrom", "harm:kqr_dqr"),
        ("harm:sourceIdentifier", _lit(f"L{n}")),
        ("a", "harm:LevelConcept"),
        ("skos:exactMatch", f"eqf:Level{n}"),
    ]
    return _block(f"harm-dqr:L{n}", triples)


def _dqr_facet_block(n: int, dim) -> str:
    suf, dtype, de_pref, en_pref, de_map, eqf_suf, predicate = dim
    triples = [
        ("a", "skos:Concept"),
        ("owl:sameAs", f"<{DQR_AUTHORITY}L{n}_{suf}>"),
        ("skos:inScheme", "harm-dqr:DQRScheme"),
        ("skos:broader", f"harm-dqr:L{n}"),
        ("skos:prefLabel", f'{_lit(f"{de_pref} {DASH} Niveau {n}", "de")} , {_lit(f"{en_pref} {DASH} Level {n}", "en")}'),
        ("skos:definition", _lit(de_map[n], "de")),
    ]
    if suf == "SocialCompetence" and n >= 6:
        triples.append(("skos:scopeNote", _lit(DQR_SOCIAL_SCOPE_DE, "de")))
    triples += [
        ("harm-dqr:descriptorType", _lit(dtype)),
        ("harm:derivedFrom", "harm:kqr_dqr"),
        ("harm:sourceIdentifier", _lit(f"L{n}_{suf}")),
        ("a", "harm:LevelConcept"),
        (f"skos:{predicate}", f"eqf:L{n}_{eqf_suf}"),
    ]
    return _block(f"harm-dqr:L{n}_{suf}", triples)


# =============================================================================
# Dateibau
# =============================================================================

def build_eqf(fine: bool) -> str:
    variant = "2D (8 Niveaus + 24 Dimensionsfacetten)" if fine else "1D (8 Niveaus)"
    out = [_header([
        f"EQF -- Variante {variant}",
        "Deskriptoren EN: OJ C 189, 15.6.2017, Annex II (Recommendation 2017/C 189/03).",
        "Deskriptoren DE: Europass, amtliche EQR-Deskriptoren Anhang II",
        "(https://europass.europa.eu/de/description-eight-eqf-levels).",
        "Erzeugt von scripts/22_build_eqf_dqr_granularity_variants.py -- nicht von Hand editieren.",
        "Reiner Referenzrahmen: keine ausgehenden Mappings ausser der 1:1-Niveaukalibrierung",
        "skos:exactMatch harm-dqr:L{n} (German EQF Referencing Report 2012/2013).",
    ])]
    out.append(_eqf_scheme())
    out.append("")
    for n in range(1, 9):
        out.append(f"# --- EQF Niveau {n} " + "-" * 40)
        out.append(_eqf_level_block(n, with_dim_links=fine))
        if fine:
            for dim in EQF_DIMS:
                out.append(_eqf_facet_block(n, dim))
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def build_dqr(fine: bool) -> str:
    variant = "2D (8 Niveaus + 32 Dimensionsfacetten)" if fine else "1D (8 Niveaus)"
    out = [_header([
        f"DQR -- Variante {variant}",
        "Niveauindikatoren DE: amtliche DQR-Matrix (data/formalized/dqr_3.ttl).",
        "Dimensionsdeskriptoren DE: data/formalized/dqr_levelProposal.ttl",
        "(verifiziert gegen https://www.dqr.de, Niveau-Detailseiten 1-8).",
        "Erzeugt von scripts/22_build_eqf_dqr_granularity_variants.py -- nicht von Hand editieren.",
        "URI-Basis harm-dqr: = http://hr-qde.org/harmonised/source/dqr/ ;",
        "je Konzept owl:sameAs auf die data.bmbf.de-Original-URI (Bruecke).",
        "Traegt den DQR<->EQF-Crosswalk (Praedikate = eval/G_struct.json):",
        "  harm-dqr:L{n}            skos:exactMatch  eqf:Level{n}",
        "  harm-dqr:L{n}_Knowledge  skos:exactMatch  eqf:L{n}_Knowledge",
        "  harm-dqr:L{n}_Skills     skos:exactMatch  eqf:L{n}_Skills",
        "  harm-dqr:L{n}_SocialCompetence / _Autonomy  skos:narrowMatch  eqf:L{n}_ResponsibilityAutonomy",
    ])]
    out.append(_dqr_scheme())
    out.append("")
    for n in range(1, 9):
        out.append(f"# --- DQR Niveau {n} " + "-" * 40)
        out.append(_dqr_level_block(n, with_dim_links=fine))
        if fine:
            for dim in DQR_DIMS:
                out.append(_dqr_facet_block(n, dim))
        out.append("")
    return "\n".join(out).rstrip() + "\n"


TARGETS = {
    "eqf_1D.ttl": lambda: build_eqf(fine=False),
    "eqf_2D.ttl": lambda: build_eqf(fine=True),
    "dqr_1D.ttl": lambda: build_dqr(fine=False),
    "dqr_2D.ttl": lambda: build_dqr(fine=True),
}


def verify(out_dir: Path) -> None:
    from rdflib import Graph, Namespace, RDF, URIRef
    from rdflib.namespace import SKOS

    HARM = Namespace("http://hr-qde.org/harmonised/")
    OWL = Namespace("http://www.w3.org/2002/07/owl#")
    EQFNS = Namespace(EQF)
    DQRNS = Namespace(DQR)
    DQRAUTH = Namespace(DQR_AUTHORITY)
    expected = {"eqf_1D.ttl": 8, "eqf_2D.ttl": 32, "dqr_1D.ttl": 8, "dqr_2D.ttl": 40}

    for name, count in expected.items():
        g = Graph()
        g.parse(str(out_dir / name), format="turtle")
        concepts = list(g.subjects(RDF.type, SKOS.Concept))
        assert len(concepts) == count, (name, len(concepts))
        kqr = HARM.kqr_eqf if name.startswith("eqf") else HARM.kqr_dqr
        for c in concepts:
            assert (c, RDF.type, HARM.LevelConcept) in g, (name, c)
            df = list(g.objects(c, HARM.derivedFrom))
            assert df == [kqr] and all(isinstance(o, URIRef) for o in df), (name, c, df)
            assert list(g.objects(c, HARM.sourceIdentifier)), (name, c)
            langs = {getattr(x, "language", None) for x in g.objects(c, SKOS.prefLabel)}
            assert {"de", "en"} <= langs, (name, c, langs)
            if name.startswith("dqr"):
                local = str(c).rsplit("/", 1)[-1]
                assert str(c).startswith(DQR), (name, c)
                assert (c, OWL.sameAs, DQRAUTH[local]) in g, (name, c, "owl:sameAs fehlt")
        print(f"  {name:12s} {len(concepts):3d} Konzepte  ok")

    # Crosswalk-Stichproben auf der DQR-Seite
    g = Graph(); g.parse(str(out_dir / "dqr_2D.ttl"), format="turtle")
    assert (DQRNS.L5, SKOS.exactMatch, EQFNS.Level5) in g
    assert (DQRNS.L5_Knowledge, SKOS.exactMatch, EQFNS.L5_Knowledge) in g
    assert (DQRNS.L5_Skills, SKOS.exactMatch, EQFNS.L5_Skills) in g
    assert (DQRNS.L5_SocialCompetence, SKOS.narrowMatch, EQFNS.L5_ResponsibilityAutonomy) in g
    assert (DQRNS.L5_Autonomy, SKOS.narrowMatch, EQFNS.L5_ResponsibilityAutonomy) in g
    n_exact = sum(1 for _ in g.triples((None, SKOS.exactMatch, None)))
    n_narrow = sum(1 for _ in g.triples((None, SKOS.narrowMatch, None)))
    print(f"  dqr_2D Crosswalk: {n_exact} exactMatch (8 Niveau + 16 Facette), {n_narrow} narrowMatch")

    g1 = Graph(); g1.parse(str(out_dir / "dqr_1D.ttl"), format="turtle")
    n_exact1 = sum(1 for _ in g1.triples((None, SKOS.exactMatch, None)))
    print(f"  dqr_1D Crosswalk: {n_exact1} exactMatch (8 Niveau)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=FORMALIZED)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for name, builder in TARGETS.items():
        (args.output_dir / name).write_text(builder(), encoding="utf-8", newline="\n")
        print(f"geschrieben: {args.output_dir / name}")
    print("Verifikation (rdflib):")
    verify(args.output_dir)


if __name__ == "__main__":
    main()
