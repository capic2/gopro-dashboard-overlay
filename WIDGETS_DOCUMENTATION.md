# Widgets Documentation - GoPro Dashboard Overlay

Documentation complète des widgets personnalisés pour créer des overlays vidéo avec données télémétrie.

## Table des matières

- [Widgets Personnalisés (Course/Karting)](#widgets-personnalisés-coursekarting)
  - [custom_calc](#custom_calc)
  - [rpm_bar](#rpm_bar)
  - [gforce_circle](#gforce_circle)
  - [lap_chronometer](#lap_chronometer)
  - [lap_times_table](#lap_times_table)
- [Widgets Standards](#widgets-standards)
- [Composants de Layout](#composants-de-layout)
- [Configuration Complète](#configuration-complète--layout-karting)
- [Données GPX Requises](#données-gpx-requises)
- [Conseils & Bonnes Pratiques](#conseils--bonnes-pratiques)
- [Dépannage](#dépannage)

---

## Widgets Personnalisés (Course/Karting)

### custom_calc

**Description** : Widget flexible permettant des calculs et affichages personnalisés via expressions Python.

**Type** : `custom_calc`

#### Attributs XML

| Attribut | Type | Défaut | Description |
|----------|------|--------|-------------|
| `x`, `y` | int | requis | Position |
| `expression` | string | requis | Expression Python à évaluer |
| `label` | string | "" | Label avant la valeur |
| `unit` | string | "" | Unité après la valeur |
| `dp` | int | 1 | Nombre de décimales |
| `size` | int | 20 | Taille de police |
| `template` | string | text | Template : `text`, `bar`, `box` |
| `align` | string | left | Alignement : `left`, `right`, `centre` |

#### Paramètres template="bar"

| Attribut | Type | Défaut | Description |
|----------|------|--------|-------------|
| `bar_width` | int | 200 | Largeur de la barre |
| `bar_height` | int | 20 | Hauteur de la barre |
| `bar_max` | int | 100 | Valeur maximum |
| `bar_color` | rgb | 0,255,100 | Couleur de remplissage |
| `bar_bg` | rgb | 50,50,50 | Couleur de fond |

#### Variables disponibles dans `expression`

##### Données instantanées

| Variable | Description | Unité |
|----------|-------------|-------|
| `alt` | Altitude | m |
| `speed` | Vitesse | m/s |
| `hr` | Fréquence cardiaque | bpm |
| `cadence` | Cadence (RPM) | rpm |
| `power` | Puissance | W |
| `temp` | Température eau | °C |
| `grad` | Gradient/pente | % |
| `dist` | Distance | m |
| `vspeed` | Vitesse verticale | m/s |

##### Données de tour

| Variable | Description |
|----------|-------------|
| `lap` | Numéro de tour actuel |
| `laptime` | Temps du tour (secondes) |
| `laptime_str` | Temps du tour formaté ("0:41.045") |
| `laptype` | Type de tour (OUT/TIMED/IN) |

##### Stats globales (via `precalc`)

| Variable | Description |
|----------|-------------|
| `precalc['max_speed']` | Vitesse max (km/h) |
| `precalc['avg_speed']` | Vitesse moyenne (km/h) |
| `precalc['max_hr']` | FC max |
| `precalc['avg_hr']` | FC moyenne |
| `precalc['max_alt']` | Altitude max (m) |
| `precalc['min_alt']` | Altitude min (m) |
| `precalc['total_gain']` | Dénivelé positif (m) |
| `precalc['total_loss']` | Dénivelé négatif (m) |
| `precalc['max_vspeed']` | Vitesse verticale max (m/s) |
| `precalc['min_vspeed']` | Vitesse verticale min (m/s) |
| `precalc['avg_vspeed']` | Vitesse verticale moyenne (m/s) |
| `precalc['best_lap']` | Temps du meilleur tour (s) |
| `precalc['best_lap_str']` | Meilleur tour formaté |
| `precalc['best_lapnum']` | Numéro du meilleur tour |

##### Fonctions utiles

| Fonction | Description |
|----------|-------------|
| `max(a, b)` | Maximum |
| `min(a, b)` | Minimum |
| `abs(x)` | Valeur absolue |
| `int(x)` | Conversion en entier |
| `float(x)` | Conversion en flottant |
| `round(x, n)` | Arrondi à n décimales |
| `str(x)` | Conversion en string |
| `state['key']` | État persistant entre frames |

#### Exemples

```xml
<!-- Vitesse en km/h -->
<component type="custom_calc"
           x="100" y="100"
           expression="speed * 3.6"
           unit=" km/h"
           dp="1"
           size="28"/>

<!-- Vitesse verticale en m/min -->
<component type="custom_calc"
           x="100" y="150"
           expression="vspeed * 60"
           label="V↑ "
           unit=" m/min"
           dp="1"
           size="24"/>

<!-- Écart au meilleur tour -->
<component type="custom_calc"
           x="100" y="200"
           expression="laptime - precalc['best_lap'] if precalc.get('best_lap') else 0"
           label="Δ "
           unit="s"
           dp="3"
           size="20"/>

<!-- Barre de FC -->
<component type="custom_calc"
           x="100" y="250"
           expression="hr"
           template="bar"
           bar_width="300"
           bar_height="30"
           bar_max="200"
           bar_color="255,50,50"
           unit=" bpm"
           dp="0"/>

<!-- Indicateur montée/descente -->
<component type="custom_calc"
           x="100" y="300"
           expression="'↑' if vspeed > 0.1 else '↓' if vspeed < -0.1 else '→'"
           size="32"/>
```

---

### rpm_bar

**Description** : Barre de régime moteur avec segments colorés et shift lights.

**Type** : `rpm_bar`

#### Attributs XML

| Attribut | Type | Défaut | Description |
|----------|------|--------|-------------|
| `x`, `y` | int | requis | Position |
| `width` | int | 400 | Largeur totale |
| `height` | int | 50 | Hauteur totale |
| `segments` | int | 17 | Nombre de segments |
| `segment_width` | int | 8 | Largeur d'un segment (px) |
| `segment_spacing` | int | 2 | Espacement entre segments (px) |
| `max_rpm` | int | 15000 | RPM maximum |
| `size` | int | 20 | Taille de police |
| `show_label` | bool | true | Afficher le label "RPM" |

#### Zones de couleur

| Zone | Couleur | Pourcentage |
|------|---------|-------------|
| Zone verte | `(0, 255, 0)` | 0-70% |
| Zone jaune | `(255, 255, 0)` | 70-85% |
| Zone orange | `(255, 165, 0)` | 85-95% |
| Zone rouge | `(255, 0, 0)` | 95-100% |

#### Exemples

```xml
<!-- Configuration standard karting -->
<component type="rpm_bar"
           x="15" y="400"
           width="400" height="50"
           segments="17"
           segment_width="8"
           segment_spacing="2"
           max_rpm="15000"
           size="20"
           show_label="true"/>

<!-- Barre compacte -->
<component type="rpm_bar"
           x="100" y="50"
           width="300" height="40"
           segments="15"
           max_rpm="12000"
           size="16"/>
```

---

### gforce_circle

**Description** : Widget circulaire affichant les forces G en temps réel.

**Type** : `gforce_circle`

#### Attributs XML

| Attribut | Type | Défaut | Description |
|----------|------|--------|-------------|
| `x`, `y` | int | requis | Position |
| `size` | int | 300 | Diamètre du cercle |
| `max_g` | float | 2.5 | Force G maximum |
| `bg_colour` | rgba | 0,0,0,220 | Couleur de fond |
| `grid_colour` | rgba | 80,80,80,150 | Couleur de la grille |
| `point_colour` | rgba | 255,50,50,255 | Couleur du point |
| `line_colour` | rgba | 255,50,50,150 | Couleur de la ligne |

#### Exemples

```xml
<!-- G-Force standard -->
<component type="gforce_circle"
           x="30" y="680"
           size="180"
           max_g="3"
           bg_colour="0,0,0,220"
           grid_colour="80,80,80,150"
           point_colour="255,50,50,255"
           line_colour="255,50,50,150"/>

<!-- G-Force grand -->
<component type="gforce_circle"
           x="100" y="100"
           size="300"
           max_g="2.5"/>
```

#### Notes

- Cercles concentriques : 0.5g, 1.0g, 1.5g, 2.0g, 2.5g
- Le point rouge indique la force G actuelle
- Axes : Vertical = Longitudinal, Horizontal = Latéral
- Les données proviennent de `accl.x` et `accl.y`

---

### lap_chronometer

**Description** : Chronomètre affichant le temps du tour en cours avec numéro et total de tours.

**Type** : `lap_chronometer`

#### Attributs XML

| Attribut | Type | Défaut | Description |
|----------|------|--------|-------------|
| `x`, `y` | int | requis | Position |
| `width` | int | 280 | Largeur du widget |
| `height` | int | 100 | Hauteur du widget |
| `size` | int | 20 | Taille de police |
| `show_lap_number` | bool | true | Afficher le numéro de tour |

#### Exemples

```xml
<!-- Chronomètre standard -->
<component type="lap_chronometer"
           x="800" y="50"
           width="280" height="100"
           size="20"
           show_lap_number="true"/>

<!-- Chronomètre compact -->
<component type="lap_chronometer"
           x="100" y="100"
           width="200" height="80"
           size="16"
           show_lap_number="false"/>
```

#### Notes

- Affiche "TOUR DE SORTIE" pour le out-lap
- Affiche "TOUR DE RENTRÉE" pour le in-lap
- Format temps : `M:SS.mmm`
- Se réinitialise automatiquement à chaque nouveau tour

---

### lap_times_table

**Description** : Tableau des temps de tour avec mise en évidence du meilleur tour et vitesse max.

**Type** : `lap_times_table`

#### Attributs XML

| Attribut | Type | Défaut | Description |
|----------|------|--------|-------------|
| `x`, `y` | int | requis | Position |
| `width` | int | 380 | Largeur du tableau |
| `max_laps` | int | 10 | Nombre max de tours visibles |
| `size` | int | 18 | Taille de police |
| `show_best` | bool | true | Mettre en évidence le meilleur tour |
| `show_max_speed` | bool | true | Afficher la vitesse max par tour |

#### Exemples

```xml
<!-- Tableau complet -->
<component type="lap_times_table"
           x="25" y="60"
           width="380"
           max_laps="8"
           size="18"
           show_best="true"
           show_max_speed="true"/>

<!-- Tableau compact sans vitesse -->
<component type="lap_times_table"
           x="50" y="100"
           width="280"
           max_laps="5"
           size="16"
           show_best="true"
           show_max_speed="false"/>
```

#### Notes

- Le meilleur tour reste affiché même s'il sort de la fenêtre
- Les tours OUT et IN sont exclus du calcul du meilleur tour
- La vitesse max est en km/h (convertie automatiquement depuis m/s)
- Les tours s'affichent uniquement **après** leur complétion

---

## Widgets Standards

### text

**Description** : Affiche du texte statique.

```xml
<component type="text" x="100" y="50" size="24" align="centre">
    MAGNY-COURS CIRCUIT
</component>
```

### metric

**Description** : Affiche une métrique avec formatage automatique.

```xml
<!-- Vitesse sans décimales -->
<component type="metric" metric="speed" units="kph" dp="0"
           x="100" y="900" size="48"/>

<!-- Fréquence cardiaque -->
<component type="metric" metric="hr" dp="0"
           x="300" y="50" size="32"/>
```

### metric_unit

**Description** : Affiche l'unité d'une métrique.

```xml
<component type="metric_unit" metric="speed" units="kph" size="18"
           x="120" y="178" align="centre">{:~P}</component>
```

### datetime

**Description** : Affiche date/heure.

```xml
<component type="datetime" format="%d/%m/%Y %H:%M:%S" size="18" x="20" y="20"/>
```

### icon

**Description** : Affiche une icône.

```xml
<component type="icon" x="0" y="0" size="36" file="heart.png"/>
```

### moving_map

**Description** : Carte GPS avec trace.

```xml
<component type="moving_map" size="200" rotate="false" corner_radius="20"/>
```

### msi

**Description** : Jauge circulaire style tableau de bord.

```xml
<component type="msi" metric="speed" units="kph"
           size="200" end="120" yellow="100" green="80" needle="1"/>
```

---

## Composants de Layout

### composite

Groupe plusieurs widgets à une position relative.

```xml
<composite x="100" y="100" name="speed_block">
    <component type="metric" metric="speed" x="0" y="0" size="48"/>
    <component type="text" x="0" y="50" size="16">km/h</component>
</composite>
```

### translate

Déplace un groupe de widgets.

```xml
<translate x="1720" y="780">
    <component type="msi" x="0" y="0" size="180"/>
</translate>
```

---

## Configuration Complète : Layout Karting

```xml
<?xml version="1.0" encoding="UTF-8"?>
<layout>
  <!-- Date -->
  <component type="datetime" format="%d/%m/%Y %H:%M:%S" size="18" x="20" y="20"/>

  <!-- Heart Rate -->
  <composite x="1780" y="20">
    <component type="icon" x="0" y="0" size="32" file="heart.png"/>
    <component type="metric" x="40" y="5" metric="hr" dp="0" size="28"/>
    <component type="metric_unit" metric="hr" x="90" y="5" size="18">{:~P}</component>
  </composite>

  <!-- Tableau des tours -->
  <component type="lap_times_table"
             x="25" y="60"
             width="380"
             max_laps="8"
             size="18"
             show_best="true"
             show_max_speed="true"/>

  <!-- Chronomètre -->
  <component type="lap_chronometer"
             x="800" y="50"
             width="280" height="100"
             size="20"
             show_lap_number="true"/>

  <!-- Vitesse + RPM -->
  <composite x="1650" y="600">
    <!-- Températures -->
    <composite x="0" y="120">
      <component type="icon" x="0" y="0" size="36" file="thermometer-1.png"/>
      <component type="metric" x="30" y="5" metric="temp" dp="0" size="22"/>
      <component type="text" x="65" y="5" size="16">°C</component>
      
      <component type="icon" x="100" y="0" size="36" file="exhaust.png"/>
      <component type="metric" x="140" y="5" metric="exhaust_temp" dp="0" size="22"/>
      <component type="text" x="180" y="5" size="16">°C</component>
    </composite>

    <!-- Jauge vitesse -->
    <composite x="0" y="180">
      <component type="msi" metric="speed" units="kph" size="200"
                 end="120" yellow="100" green="80" needle="1"/>
      <component type="metric" metric="calculated_gear" x="100" y="45" size="30" dp="0"/>
      <component type="metric" metric="speed" units="kph" dp="0" size="40" x="100" y="140"/>
      <component type="metric_unit" metric="speed" units="kph" size="18"
                 x="120" y="178">{:~P}</component>
    </composite>

    <!-- Barre RPM -->
    <component type="rpm_bar"
               x="15" y="400"
               width="400" height="50"
               segments="17"
               max_rpm="15000"
               size="20"/>
  </composite>

  <!-- G-Force -->
  <component type="gforce_circle"
             x="30" y="680"
             size="180"
             max_g="3"/>

  <!-- Carte -->
  <translate x="20" y="850">
    <component type="moving_map" size="200" rotate="false" corner_radius="20"/>
  </translate>
</layout>
```

---

## Données GPX Requises

Pour utiliser ces widgets, votre fichier GPX doit contenir les extensions suivantes :

### Extensions TrackPointExtension (namespace `gpxtpx`)

```xml
<gpxtpx:TrackPointExtension>
  <gpxtpx:speed>13.203083</gpxtpx:speed>
  <gpxtpx:hr>142</gpxtpx:hr>
  <gpxtpx:cad>10649</gpxtpx:cad>
  <gpxtpx:atemp>42.84</gpxtpx:atemp>
  <gpxtpx:exhaust_temp>265.84</gpxtpx:exhaust_temp>
  <gpxtpx:calculated_gear>1</gpxtpx:calculated_gear>
  <gpxtpx:vspeed>0.125000</gpxtpx:vspeed>
  
  <!-- Données de tour -->
  <gpxtpx:lap>1</gpxtpx:lap>
  <gpxtpx:laptime>53.064</gpxtpx:laptime>
  <gpxtpx:laptime_str>0:53.064</gpxtpx:laptime_str>
  <gpxtpx:laptype>TIMED</gpxtpx:laptype>
</gpxtpx:TrackPointExtension>
```

### Extensions Acceleration/Gyroscope (namespace `gpxpx`)

```xml
<gpxpx:Acceleration>
  <gpxpx:x>0.090300</gpxpx:x>
  <gpxpx:y>-0.415000</gpxpx:y>
  <gpxpx:z>-1.238800</gpxpx:z>
</gpxpx:Acceleration>

<gpxpx:Gyroscope>
  <gpxpx:x>0.123456</gpxpx:x>
  <gpxpx:y>0.234567</gpxpx:y>
  <gpxpx:z>0.345678</gpxpx:z>
</gpxpx:Gyroscope>
```

---

## Conseils & Bonnes Pratiques

### 1. Organisation du Layout

- Utilisez `<composite>` pour grouper les widgets liés
- Nommez vos composites (`name="speed_block"`) pour faciliter la maintenance
- Commentez votre XML

### 2. Performance

- Limitez le nombre de widgets à l'écran
- Utilisez `dp` (décimales) raisonnablement
- Évitez les expressions complexes dans `custom_calc`
- `max_laps` raisonnable pour `lap_times_table` (8-10 max)

### 3. Lisibilité

- Ajoutez toujours un `stroke` (contour noir) sur le texte blanc
- Utilisez des fonds semi-transparents : `bg_colour="0,0,0,180"`
- Espacement cohérent : multiples de 10 ou 20px
- Tailles de police cohérentes

### 4. Résolutions

- **1080p** : 16-24px pour texte, 180-200px pour jauges
- **4K** : Doublez toutes les valeurs
- Testez sur la résolution cible !

### 5. Données Karting

- `rpm` est mappé sur `cad` dans le GPX
- Le `calculated_gear` est calculé depuis le rapport
- Tours : `lap`, `laptime`, `laptype` disponibles
- Vitesse verticale : `vspeed` en m/s (multiplier par 60 pour m/min)

---

## Dépannage

### Widget ne s'affiche pas

1. Vérifiez le type : `type="rpm_bar"`
2. Vérifiez les coordonnées : dans le cadre vidéo ?
3. Ajoutez des prints de debug dans le widget
4. Vérifiez que les données GPX sont présentes

### Erreur "attribute not found"

- Assurez-vous que l'attribut existe dans `@allow_attributes`
- Vérifiez la factory dans `layout_xml.py`

### Valeurs incorrectes

- Vérifiez le mapping dans GPX (rpm → cad, etc.)
- Utilisez `custom_calc` avec prints pour débugger
- Vérifiez les unités (m/s vs km/h, etc.)

### Performance lente

- Réduisez `segments` dans `rpm_bar`
- Réduisez `max_laps` dans `lap_times_table`
- Désactivez les fonctionnalités inutilisées
- Simplifiez les expressions `custom_calc`

### Vitesse verticale toujours à 0

- Vérifiez que `vspeed` est dans le GPX
- Vérifiez que `gpx.py` parse `vspeed`
- Vérifiez la conversion m/s (valeurs très petites)

---

## Scripts Utiles

### Conversion MyChron CSV → GPX

```bash
python mychron_to_gpx.py session.csv --merge-gpx gopro.gpx
```

### Merge OSV (accéléromètre GoPro) + GPX

```bash
python osv_merge_gpx.py video.OSV track.gpx merged.gpx
```

### Génération overlay

```bash
gopro-dashboard.py --gpx merged.gpx --input video.MP4 --output overlay.MP4 --layout karting.xml
```

---

**Version** : 2.0  
**Dernière mise à jour** : 02/01/2026  
**Auteur** : Vincent Capicotto (@capic2)  
**Projet** : [github.com/capic2/gopro-dashboard-overlay](https://github.com/capic2/gopro-dashboard-overlay)
