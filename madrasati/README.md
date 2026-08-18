# Madrasati — مدرستي

Logiciel de gestion d'école pour le Maroc 🇲🇦, construit avec Django.

**School management software for Morocco**: student registration, tuition
tracking in dirhams, Moroccan payroll (CNSS, AMO, IR), fully bilingual
French/Arabic interface with RTL support.

## Fonctionnalités

### 🎓 Élèves
- Fiche élève complète : état civil bilingue (français/arabe), âge calculé
  automatiquement, **code Massar**, lieu de naissance, observations médicales,
  établissement précédent.
- Tuteurs (père, mère, tuteur légal) avec CIN, téléphone (validation des
  numéros marocains `06…`/`+212…`) et profession.
- Inscriptions par classe et par année scolaire, avec remises (fratrie, bourse).
- Suivi des absences/retards et des notes (sur 20, par semestre).

### 🏫 Structure scolaire marocaine
- Niveaux préconfigurés : préscolaire, primaire (1AP–6AP), collège (1AC–3AC),
  lycée (TC, 1BAC, 2BAC), avec noms arabes officiels.
- Classes par niveau et par année scolaire (septembre → juillet), matières
  bilingues avec coefficients.

### 💰 Frais de scolarité (MAD)
- Formules de frais par niveau : frais d'inscription, mensualité, assurance
  scolaire, nombre de mensualités.
- Paiements en dirhams : espèces, chèque, virement, carte — avec **reçus
  numérotés automatiquement** (`REC-2026-00001`) et **reçu imprimable
  bilingue**.
- Suivi des mois impayés par élève, encaissements du mois sur le tableau
  de bord.

### 🧾 Paie marocaine
- Employés : matricule, CIN, n° CNSS, RIB, salaire de base + primes,
  personnes à charge.
- Calcul conforme à la réglementation marocaine (Loi de finances 2025) :
  - **CNSS** part salariale 4,48 % (plafond 6 000 DH) ;
  - **AMO** 2,26 % ;
  - **Frais professionnels** 35 % / 25 % (plafond 2 916,67 DH/mois) ;
  - **IR** barème mensuel progressif 2025 ;
  - **Charges de famille** 41,67 DH/mois par personne (max 6) ;
  - Coût employeur (CNSS patronale, allocations familiales, AMO, taxe de
    formation professionnelle).
- Cycles de paie mensuels : génération des bulletins en un clic, validation,
  marquage « payé », **bulletin de paie imprimable bilingue**.
- Les taux sont centralisés dans [`hr/payroll.py`](hr/payroll.py) pour suivre
  les futures lois de finances.

### 🌍 Localisation
- Interface **français** (par défaut) et **arabe** avec affichage RTL
  automatique.
- Fuseau horaire `Africa/Casablanca`, montants en dirhams (DH),
  année scolaire marocaine, mois affichés à la marocaine (shtanbir/دجنبر…).

## Démarrage

```bash
git clone https://github.com/bmokhtari/SchoolRepo.git && cd SchoolRepo
pip install -r requirements.txt
python manage.py migrate
python manage.py seed            # niveaux marocains, matières, frais
# ou : python manage.py seed --demo   (avec élèves/employés d'exemple)
python manage.py createsuperuser
python manage.py runserver
```

Puis ouvrir <http://127.0.0.1:8000/> (redirige vers l'interface de gestion).

Pour recompiler les traductions arabes après modification :

```bash
python manage.py makemessages -l ar
python manage.py compilemessages   # nécessite gettext
```

## Hébergement

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/bmokhtari/SchoolRepo)

GitHub ne peut pas exécuter l'application (GitHub Pages ne sert que des
sites statiques) : il faut un hébergeur Python. Le dépôt est prêt pour un
déploiement en un clic sur **Render** — bouton ci-dessus, ou manuellement :

1. Créer un compte sur <https://render.com> (offre gratuite).
2. **New +** → **Blueprint** → connecter ce dépôt GitHub.
3. Render lit [`render.yaml`](render.yaml) : build, migrations, données de
   base et compte `admin` sont créés automatiquement (mot de passe généré,
   visible dans l'onglet *Environment* du service).

L'application est alors accessible sur `https://madrasati.onrender.com`
(ou similaire). Fonctionne aussi sur Railway ou Heroku via le
[`Procfile`](Procfile).

> 💡 Sur l'offre gratuite de Render, le disque est éphémère : la base
> SQLite est réinitialisée à chaque déploiement. Pour des données
> persistantes, créer une base **PostgreSQL** (Render en propose) et
> définir la variable d'environnement `DATABASE_URL` — elle est prise en
> charge automatiquement.

### Auto-hébergement (Docker)

Pour héberger soi-même (PC de l'école, VPS…) avec données persistantes :

```bash
docker compose up -d
```

Puis ouvrir <http://localhost:8000> (compte `admin`, mot de passe défini
dans [`docker-compose.yml`](docker-compose.yml) — à changer, ainsi que
`DJANGO_SECRET_KEY`, avant toute mise en production). La base SQLite est
conservée dans un volume Docker entre les redémarrages.

> GitHub ne propose pas d'hébergement applicatif : GitHub Pages ne sert
> que des sites statiques, et les « self-hosted runners » servent à la CI,
> pas à faire tourner une application.

## Tests

```bash
python manage.py test
```

Les tests couvrent notamment le calcul de paie (tranches IR, plafond CNSS,
déductions familiales), la numérotation des reçus et le suivi des impayés.

## Structure

| App        | Rôle                                                        |
|------------|-------------------------------------------------------------|
| `core`     | Années scolaires, niveaux, classes, matières, tableau de bord |
| `students` | Élèves, tuteurs, inscriptions, absences, notes               |
| `finance`  | Formules de frais, paiements, reçus                          |
| `hr`       | Employés, cycles de paie, bulletins (calcul CNSS/AMO/IR)     |

> ⚠️ Les paramètres de paie et d'IR reflètent la réglementation à la date du
> développement ; vérifiez chaque loi de finances avant usage en production.
