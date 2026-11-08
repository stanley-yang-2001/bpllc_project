"""Everyday nouns whose gender is not in doubt, for the article and noun checks (7 Nov 2026).

Only nouns that have ONE gender in everyday use are listed, so a mismatch is a real mistake: "el/la" nouns like "el/la capital", French
"enfant" (un or une), "livre" (book or pound) and German nouns that double as verbs ("Reise" / "ich reise") are left out on purpose.
A noun missing here is simply not checked. The first block of each language is the starter packs (tutor_core/starter.py), then
common words. Add words by editing the strings; a word in two lists, or one that is not a noun, fails tests/test_grammar_rules.py.
"""
from __future__ import annotations

_RAW = {
    "es": {
        "m": "libro gato perro amigo hermano hijo niño padre hombre señor chico vaso plato queso zapato pan café té arroz pescado huevo "
             "coche tren avión árbol jardín parque mercado trabajo día mapa problema sistema programa tema idioma clima planeta viaje "
             "lápiz papel color sol cielo río pueblo teléfono regalo desayuno almuerzo mundo año cuaderno bolso sombrero restaurante "
             "hotel autobús barco queso jugo vino",
        "f": "casa mesa silla ventana puerta escuela ciudad calle tienda familia madre hija niña amiga manzana leche noche tarde comida "
             "cena fiesta foto moto mano flor luz paz voz vez canción lección estación habitación cocina playa plaza carta historia "
             "semana ropa camisa tarea pregunta respuesta música lengua sopa fruta naranja bicicleta mochila falda",
    },
    "fr": {
        "m": "pain café thé riz poisson fromage ami père garçon homme chat chien frère fils jardin parc marché magasin travail jour matin "
             "soir temps cadeau gâteau repas déjeuner dîner train avion arbre ciel soleil village pays monde téléphone stylo crayon "
             "cahier papier sac verre couteau œuf lait fruit légume restaurant hôtel bateau vélo bus mois an anniversaire nom",
        "f": "eau pomme mère fille famille maison école ville rue voiture table chaise fenêtre porte cuisine chambre salle nuit journée "
             "soirée semaine fête carte lettre histoire musique langue soupe salade tarte banane orange fleur plage place classe leçon "
             "question réponse amie gare montagne rivière forêt mer lune étoile",
    },
    "it": {
        "m": "libro amico padre bambino ragazzo gatto cane pesce pane caffè tè riso formaggio latte uovo lavoro giorno mattino albero "
             "giardino parco mercato negozio treno aereo cielo sole mare fiume paese mondo telefono regalo compleanno vino bicchiere "
             "piatto tavolo letto nome anno mese ristorante albergo problema sistema programma tema clima panorama schema dramma",
        "f": "madre casa scuola città strada famiglia mela acqua amica bambina ragazza sera notte giornata settimana festa carta lettera "
             "storia musica lingua zuppa frutta arancia fiore spiaggia piazza lezione domanda risposta stazione montagna macchina "
             "finestra porta cucina camera sedia borsa gonna",
    },
    "pt": {
        "m": "livro amigo pai menino gato cachorro pão café chá arroz peixe queijo leite ovo trabalho dia carro trem avião jardim parque "
             "mercado país mundo telefone presente aniversário copo prato sapato ano mês nome restaurante hotel problema mapa sistema "
             "tema programa idioma clima planeta sol céu rio",
        "f": "mãe casa escola cidade rua loja família maçã água amiga menina noite tarde manhã semana festa carta história música língua "
             "sopa fruta laranja flor praia praça lição pergunta resposta estação montanha mesa cadeira janela porta cozinha comida foto "
             "moto mão luz paz voz vez criança pessoa",
    },
    # German: nouns whose plural is spelled like the singular (Käse, Kuchen, Mädchen, Fenster, Zimmer, Essen, Gemüse, Wetter) are left
    # out, because "die" before them can be a plural; so are nouns that are also a verb form (Reise, Spiel) or an adjective (Liebe).
    "de": {
        "m": "Freund Vater Bruder Mann Junge Hund Tisch Stuhl Fisch Apfel Reis Kaffee Tee Wein Saft Tag Abend Garten Park Markt Zug Baum "
             "Himmel Berg Fluss Brief Hunger Platz Bahnhof Geburtstag Urlaub Schuh Salat Kopf Name Film",
        "f": "Mutter Schwester Frau Familie Schule Stadt Straße Arbeit Milch Katze Tür Nacht Woche Zeit Tasche Uhr Küche Blume Zeitung "
             "Banane Orange Suppe Torte Wohnung Party Freundin Tochter Stunde Kirche Brücke",
        "n": "Kind Haus Buch Brot Wasser Ei Geschäft Auto Bett Frühstück Geschenk Jahr Telefon Hotel "
             "Restaurant Bier Obst Fleisch Glas Heft Café Land Dorf Bild Lied Tier Kino Museum",
    },
}

def _build() -> dict:
    out = {}
    for code, genders in _RAW.items():
        table = {}
        for gender, words in genders.items():
            for word in words.split():
                key = word if code == "de" else word.casefold()
                table.setdefault(key, gender)
        out[code] = table
    return out


NOUNS = _build()


def duplicates() -> list[tuple[str, str]]:
    """(language, word) listed under two genders: always empty (tests/test_grammar_rules.py)."""
    seen, bad = {}, []
    for code, genders in _RAW.items():
        for gender, words in genders.items():
            for word in words.split():
                key = (code, word.casefold())
                if key in seen and seen[key] != gender:
                    bad.append(key)
                seen.setdefault(key, gender)
    return bad
