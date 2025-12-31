# Documentation des Widgets - GoPro Dashboard Overlay

Documentation complète des widgets disponibles pour créer des overlays vidéo personnalisés.

## Table des matières

- [Widgets Personnalisés (Racing/Karting)](#widgets-personnalisés-racingkarting)
  - [custom_calc](#custom_calc)
  - [rpm_bar](#rpm_bar)
  - [gforce](#gforce)
  - [lap_chronometer](#lap_chronometer)
  - [lap_times_table](#lap_times_table)
- [Widgets Standards](#widgets-standards)
- [Composants de Layout](#composants-de-layout)
- [Configuration Complète](#configuration-complète)
- [Fonctions Python](#fonctions-python)
- [Tips & Best Practices](#tips--best-practices)
- [Dépannage](#dépannage)

---

## Widgets Personnalisés (Racing/Karting)

### custom_calc

**Description** : Widget permettant d'afficher des valeurs calculées avec des expressions Python personnalisées.

**Type** : `custom_calc`

#### Attributs XML

| Attribut | Type | Défaut | Description |
|----------|------|--------|-------------|
| `x`, `y` | int | - | Position (obligatoire) |
| `expression` | string | - | Expression Python (obligatoire) |
| `size` | int | 18 | Taille police |
| `align` | string | "left" | Alignement |

#### Variables disponibles

##### Métriques courantes
- `speed` - Vitesse (km/h)
- `rpm`, `cad` - RPM moteur
- `temp` - Température
- `gear` - Rapport
- `lap` - Numéro de tour
- `laptime` - Temps total
- `laptime_str` - Temps formaté
- `laptype` - Type de tour

##### Accélérations
- `accl.x`, `accl.y`, `accl.z` - Accélérations (g)

##### Stats pré-calculées
```python
precalc['max_speed']
precalc['max_rpm']
precalc['max_temp']
precalc['max_lat_acc']
precalc['max_lon_acc']
precalc['max_g_combined']
```

##### Fonctions
```python
format_speed(speed)
format_temp(temp)
format_rpm(rpm)
format_g(g_value)
format_laptime(seconds)
```

#### Exemples

```xml
<!-- Vitesse simple -->
<component type="custom_calc" 
           expression="f'{speed:.0f} km/h'" 
           x="100" y="50" size="32"/>

<!-- Vitesse max -->
<component type="custom_calc" 
           expression="f'Max: {precalc.get(\"max_speed\", 0):.0f} km/h'" 
           x="100" y="90" size="20"/>

<!-- G combiné -->
<component type="custom_calc" 
           expression="format_g(math.sqrt(accl.x**2 + accl.y**2))" 
           x="300" y="100" size="24"/>

<!-- Rapport -->
<component type="custom_calc" 
           expression="f'Gear {int(gear)}' if gear > 0 else 'N'" 
           x="150" y="200" size="30"/>
```

---

### rpm_bar

**Description** : Barre RPM segmentée style racing avec dégradé de couleurs.

**Type** : `rpm_bar`

#### Attributs XML

| Attribut | Type | Défaut | Description |
|----------|------|--------|-------------|
| `x`, `y` | int | - | Position |
| `width` | int | 300 | Largeur |
| `height` | int | 50 | Hauteur |
| `segments` | int | 24 | Nombre de barres |
| `segment_width` | int | 8 | Largeur barre (px) |
| `segment_spacing` | int | 2 | Espacement (px) |
| `max_rpm` | int | 15000 | RPM max |
| `size` | int | 16 | Taille police |
| `show_value` | bool | true | Afficher valeur |
| `show_label` | bool | true | Afficher label |

#### Dégradé de couleurs
- 0-30% : Cyan → Vert
- 30-50% : Vert → Jaune
- 50-70% : Jaune → Orange
- 70-100% : Orange → Rouge

#### Exemples

```xml
<!-- Standard -->
<component type="rpm_bar" 
           x="50" y="900" 
           width="300" height="50" 
           segments="24" 
           max_rpm="15000" 
           size="20"/>

<!-- Compact -->
<component type="rpm_bar" 
           x="800" y="950" 
           width="250" height="40" 
           segments="16" 
           max_rpm="12000" 
           show_label="false"/>
```

---

### gforce

**Description** : Cercle G-Force avec point mobile en temps réel.

**Type** : `gforce`

#### Attributs XML

| Attribut | Type | Défaut | Description |
|----------|------|--------|-------------|
| `x`, `y` | int | - | Position |
| `size` | int | 300 | Diamètre |
| `max_g` | float | 2.5 | G maximum |
| `font_size` | int | 14 | Taille police |

#### Exemples

```xml
<!-- Standard -->
<component type="gforce" 
           x="1600" y="50" 
           size="300" 
           max_g="2.5" 
           font_size="14"/>

<!-- Compact -->
<component type="gforce" 
           x="50" y="50" 
           size="200" 
           max_g="2.0"/>
```

---

### lap_chronometer

**Description** : Chronomètre du tour en cours.

**Type** : `lap_chronometer`

#### Attributs XML

| Attribut | Type | Défaut | Description |
|----------|------|--------|-------------|
| `x`, `y` | int | - | Position |
| `width` | int | 280 | Largeur |
| `height` | int | 100 | Hauteur |
| `size` | int | 16 | Taille police |
| `show_lap_number` | bool | true | Afficher "TOUR X" |

#### Exemples

```xml
<component type="lap_chronometer" 
           x="800" y="50" 
           width="280" height="100" 
           size="20" 
           show_lap_number="true"/>
```

---

### lap_times_table

**Description** : Tableau des temps de tour avec meilleur tour.

**Type** : `lap_times_table`

#### Attributs XML

| Attribut | Type | Défaut | Description |
|----------|------|--------|-------------|
| `x`, `y` | int | - | Position |
| `width` | int | 300 | Largeur |
| `max_laps` | int | 10 | Tours affichés |
| `size` | int | 16 | Taille police |
| `show_best` | bool | true | Étoile meilleur |

#### Exemples

```xml
<component type="lap_times_table" 
           x="30" y="300" 
           width="280" 
           max_laps="8" 
           size="18" 
           show_best="true"/>
```

---

## Widgets Standards

### text

```xml
<component type="text" x="100" y="50" size="24" align="centre">
    CIRCUIT DE MAGNY-COURS
</component>
```

### metric

```xml
<component type="metric" metric="speed" units="kph" dp="0" 
           x="100" y="900" size="48"/>
```

### chart

```xml
<component type="chart" 
           x="100" y="600" 
           width="400" height="100" 
           metric="speed" 
           samples="128"/>
```

### map

```xml
<component type="map" 
           x="50" y="50" 
           size="300" 
           zoom="16"/>
```

### msi

```xml
<component type="msi" 
           x="960" y="540" 
           metric="speed" 
           units="kph" 
           size="200" 
           end="200"/>
```

---

## Composants de Layout

### composite

```xml
<composite x="100" y="100" name="speed_block">
    <component type="metric" metric="speed" x="0" y="0" size="48"/>
</composite>
```

### frame

```xml
<frame x="50" y="50" width="300" height="100" 
       bg="0,0,0,180" 
       outline="255,255,255,100" 
       cr="10"/>
```

---

## Configuration Complète : Layout Karting

```xml
<?xml version="1.0" encoding="UTF-8"?>
<layout>
    <composite x="1720" y="780" name="speed_rpm_block">
        <component type="msi" metric="speed" units="kph" 
                   x="0" y="0" size="180" 
                   end="120" yellow="100" green="80"/>
        
        <component type="metric" metric="speed" units="kph" dp="0" 
                   x="90" y="140" size="40" align="centre"/>
        
        <component type="custom_calc" 
                   expression="f'{int(gear)}' if gear > 0 else 'N'" 
                   x="90" y="45" size="30" align="centre"/>
        
        <component type="rpm_bar" 
                   x="0" y="200" 
                   width="300" height="50" 
                   segments="24" max_rpm="15000"/>
    </composite>

    <component type="gforce" 
               x="1600" y="50" 
               size="300" max_g="2.5"/>

    <component type="lap_chronometer" 
               x="800" y="50" 
               width="280" height="100" size="20"/>

    <component type="lap_times_table" 
               x="30" y="300" 
               width="280" max_laps="8" size="18"/>

    <component type="map" 
               x="50" y="700" 
               size="300" zoom="17" corner="10"/>
</layout>
```

---

## Fonctions Python disponibles

### Module math
```python
math.sqrt(x)
math.pow(x, y)
math.floor(x)
math.ceil(x)
```

### Formatage
```python
format_speed(120.5)     # "120 km/h"
format_temp(78.3)       # "78°C"
format_rpm(12450)       # "12450 RPM"
format_g(2.34)          # "2.3g"
format_laptime(41.045)  # "0:41.045"
```

### Conditionnels
```python
result = "Rapide" if speed > 100 else "Lent"
value = laptime if laptime else 0
max_speed = precalc.get('max_speed', 0)
```

---

## Tips & Best Practices

### Organisation
- Utilisez `<composite>` pour grouper
- Nommez vos composites

### Performance
- Limitez les widgets visibles
- `max_laps` raisonnable (8-10)

### Lisibilité
- Contour noir sur texte blanc
- Fonds semi-transparents
- Espacement cohérent (10/20px)

### Résolutions
- **1080p** : 16-24px texte, 180-200px jauges
- **4K** : Doublez les valeurs

### Données Karting
- `rpm` mappé sur `cad`
- `gear` dans `calculated_gear`
- Tours : `lap`, `laptime`, `laptype`

---

## Dépannage

### Widget invisible
1. Type correct ?
2. Coordonnées dans le cadre ?
3. Prints de debug

### Erreur attribut
- Dans `@allow_attributes` ?
- Factory correcte ?

### Valeurs incorrectes
- Mapping GPX correct ?
- Debug avec `custom_calc`

### Performance
- Réduire `segments`
- Réduire `max_laps`

---

**Version** : 1.0.0  
**Date** : 31 Décembre 2025  
**Auteur** : Vincent Capicotto (@capic2)  
**Projet** : [github.com/capic2/gopro-dashboard-overlay](https://github.com/capic2/gopro-dashboard-overlay)
