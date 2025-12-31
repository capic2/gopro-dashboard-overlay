# Widgets Documentation - GoPro Dashboard Overlay

Complete documentation of available widgets for creating custom video overlays.

## Table of Contents

- [Custom Widgets (Racing/Karting)](#custom-widgets-racingkarting)
  - [custom_calc](#custom_calc)
  - [rpm_bar](#rpm_bar)
  - [gforce](#gforce)
  - [lap_chronometer](#lap_chronometer)
  - [lap_times_table](#lap_times_table)
- [Standard Widgets](#standard-widgets)
- [Layout Components](#layout-components)
- [Complete Configuration](#complete-configuration--karting-layout)
- [Python Functions](#python-functions)
- [Tips & Best Practices](#tips--best-practices)
- [Troubleshooting](#troubleshooting)

---

## Custom Widgets (Racing/Karting)

### custom_calc

**Description**: Widget to display calculated values with custom Python expressions. Supports pre-calculated statistics over the entire session.

**Type**: `custom_calc`

#### XML Attributes

| Attribute | Type | Default | Description |
|----------|------|--------|-------------|
| `x`, `y` | int | - | Position (required) |
| `expression` | string | - | Python expression (required) |
| `size` | int | 18 | Font size |
| `align` | string | "left" | Alignment: "left", "centre", "right" |

#### Available Variables in `expression`

##### Common Metrics
- `speed` - Current speed (km/h)
- `rpm`, `cad` - Engine RPM
- `temp` - Water/engine temperature
- `gear` - Gear ratio
- `lap` - Current lap number
- `laptime` - Total lap time
- `laptime_str` - Formatted time (e.g., "0:41.045")
- `laptype` - Lap type (`'OUT'`, `'TIMED'`, `'IN'`)

##### Accelerations
- `accl.x`, `accl.y`, `accl.z` - Accelerations (g)
- `gps_lat_acc`, `gps_lon_acc` - GPS lateral/longitudinal acceleration

##### Pre-calculated Statistics (`precalc`)
```python
precalc['max_speed']        # Session max speed
precalc['max_rpm']          # Max RPM
precalc['max_temp']         # Max temperature
precalc['max_lat_acc']      # Max lateral acceleration
precalc['max_lon_acc']      # Max longitudinal acceleration
precalc['max_g_combined']   # Max combined G
```

##### Utility Functions
```python
format_speed(speed)          # Format: "125 km/h"
format_temp(temp)            # Format: "78°C"
format_rpm(rpm)              # Format: "12500 RPM"
format_g(g_value)            # Format: "2.5g"
format_laptime(seconds)      # Format: "0:41.045"
```

#### Examples

```xml
<!-- Simple speed -->
<component type="custom_calc" 
           expression="f'{speed:.0f} km/h'" 
           x="100" y="50" size="32"/>

<!-- Session max speed -->
<component type="custom_calc" 
           expression="f'Max: {precalc.get(\"max_speed\", 0):.0f} km/h'" 
           x="100" y="90" size="20"/>

<!-- Combined G-force -->
<component type="custom_calc" 
           expression="format_g(math.sqrt(accl.x**2 + accl.y**2))" 
           x="300" y="100" size="24"/>

<!-- Gear ratio -->
<component type="custom_calc" 
           expression="f'Gear {int(gear)}' if gear > 0 else 'N'" 
           x="150" y="200" size="30"/>

<!-- Formatted lap time -->
<component type="custom_calc" 
           expression="laptime_str if laptime_str else '-'" 
           x="400" y="120" size="26"/>
```

---

### rpm_bar

**Description**: Racing-style segmented RPM bar with increasing bar heights and color gradient (cyan → green → yellow → orange → red).

**Type**: `rpm_bar`

#### XML Attributes

| Attribute | Type | Default | Description |
|----------|------|--------|-------------|
| `x`, `y` | int | - | Position (required) |
| `width` | int | 300 | Total width |
| `height` | int | 50 | Total height |
| `segments` | int | 24 | Number of bars |
| `segment_width` | int | 8 | Bar width (px) |
| `segment_spacing` | int | 2 | Spacing between bars (px) |
| `max_rpm` | int | 15000 | Maximum RPM |
| `size` | int | 16 | Font size for labels |
| `show_value` | bool | true | Display RPM value on left |
| `show_label` | bool | true | Display "RPM X1000" at bottom |

#### Visual Rendering

```
 12.5  ▁▂▃▄▅▆▇█▇▆▅▄▃▂▁░░░░░░░
       1   5   10  15
       RPM X1000
```

#### Color Gradient
- **Inactive bars**: Dark gray (40, 40, 40)
- **Active gradient**:
  - 0-30%: Cyan → Green
  - 30-50%: Green → Yellow
  - 50-70%: Yellow → Orange
  - 70-100%: Orange → Red

#### Examples

```xml
<!-- Standard configuration -->
<component type="rpm_bar" 
           x="50" y="900" 
           width="300" height="50" 
           segments="24" 
           max_rpm="15000" 
           size="20"/>

<!-- Compact bar (fewer segments) -->
<component type="rpm_bar" 
           x="800" y="950" 
           width="250" height="40" 
           segments="16" 
           segment_width="10" 
           max_rpm="12000" 
           show_label="false"/>

<!-- Large HD bar -->
<component type="rpm_bar" 
           x="100" y="1800" 
           width="600" height="80" 
           segments="30" 
           segment_width="16" 
           segment_spacing="3" 
           max_rpm="18000"/>
```

---

### gforce

**Description**: G-Force circle showing lateral and longitudinal accelerations with a real-time moving point.

**Type**: `gforce`

#### XML Attributes

| Attribute | Type | Default | Description |
|----------|------|--------|-------------|
| `x`, `y` | int | - | Top-left position |
| `size` | int | 300 | Circle diameter |
| `max_g` | float | 2.5 | Maximum G displayed |
| `font_size` | int | 14 | Font size for labels |

#### Visual Rendering

```
        Brake
         ↑
         │
    ─────┼─────
         │
         ↓
       Accel
```

- **Concentric circles**: 0.5g, 1.0g, 1.5g, 2.0g, 2.5g
- **Red point**: Current G position
- **Line**: From center to current point
- **Labels**: "Brake" (top), "Accel" (bottom)

#### Examples

```xml
<!-- Standard configuration -->
<component type="gforce" 
           x="1600" y="50" 
           size="300" 
           max_g="2.5" 
           font_size="14"/>

<!-- Small compact circle -->
<component type="gforce" 
           x="50" y="50" 
           size="200" 
           max_g="2.0" 
           font_size="12"/>

<!-- Large 4K circle -->
<component type="gforce" 
           x="3200" y="100" 
           size="600" 
           max_g="3.0" 
           font_size="20"/>
```

---

### lap_chronometer

**Description**: Chronometer displaying elapsed time of current lap with lap number and type (OUT LAP, TIMED, IN LAP).

**Type**: `lap_chronometer`

#### XML Attributes

| Attribute | Type | Default | Description |
|----------|------|--------|-------------|
| `x`, `y` | int | - | Position (required) |
| `width` | int | 280 | Width |
| `height` | int | 100 | Height |
| `size` | int | 16 | Base font size |
| `show_lap_number` | bool | true | Display "LAP X" |

#### Visual Rendering

```
┌──────────────────┐
│     LAP 3        │
│                  │
│   0:32.456       │ (2.5x larger)
│                  │
└──────────────────┘
```

#### Examples

```xml
<!-- Standard configuration -->
<component type="lap_chronometer" 
           x="800" y="50" 
           width="280" height="100" 
           size="20" 
           show_lap_number="true"/>

<!-- Compact without number -->
<component type="lap_chronometer" 
           x="1600" y="900" 
           width="220" height="80" 
           size="16" 
           show_lap_number="false"/>
```

---

### lap_times_table

**Description**: Table displaying lap times progressively, with best lap highlighted.

**Type**: `lap_times_table`

#### XML Attributes

| Attribute | Type | Default | Description |
|----------|------|--------|-------------|
| `x`, `y` | int | - | Position (required) |
| `width` | int | 300 | Table width |
| `max_laps` | int | 10 | Max laps displayed |
| `size` | int | 16 | Font size |
| `show_best` | bool | true | Show star on best lap |

#### Visual Rendering

```
┌────────────────────────┐
│ LAP           TIME     │
├────────────────────────┤
│  1           0:53.064  │
│  2           0:44.147  │
│  3           0:44.060  │
│  4           0:42.303  │
│  5 ★         0:41.045  │ ← Best lap
│  6           0:42.513  │
│  7           0:41.349  │
│  8           0:42.298  │
└────────────────────────┘
```

#### Examples

```xml
<!-- Standard configuration -->
<component type="lap_times_table" 
           x="30" y="300" 
           width="280" 
           max_laps="8" 
           size="18" 
           show_best="true"/>

<!-- Compact (last 5 laps) -->
<component type="lap_times_table" 
           x="1650" y="700" 
           width="250" 
           max_laps="5" 
           size="14"/>
```

---

## Standard Widgets

### text

**Description**: Display static text.

**Type**: `text`

#### XML Attributes

| Attribute | Type | Default | Description |
|----------|------|--------|-------------|
| `x`, `y` | int | - | Position |
| `size` | int | 16 | Font size |
| `align` | string | "left" | "left", "centre", "right" |
| `rgb` | string | "255,255,255" | RGB color |
| `outline` | string | "0,0,0" | Outline color |
| `outline_width` | int | 2 | Outline thickness |

#### Example

```xml
<component type="text" x="100" y="50" size="24" align="centre">
    MAGNY-COURS CIRCUIT
</component>
```

---

### metric

**Description**: Display a metric with automatic formatting.

**Type**: `metric`

#### XML Attributes

| Attribute | Type | Default | Description |
|----------|------|--------|-------------|
| `x`, `y` | int | - | Position |
| `metric` | string | - | Metric name: `speed`, `alt`, `hr`, etc. |
| `units` | string | auto | Units: `kph`, `mph`, `mps`, `metres` |
| `dp` | int | 1 | Decimal places |
| `size` | int | 18 | Font size |
| `align` | string | "left" | Alignment |

#### Examples

```xml
<!-- Speed without decimals -->
<component type="metric" metric="speed" units="kph" dp="0" 
           x="100" y="900" size="48"/>

<!-- Altitude -->
<component type="metric" metric="alt" units="metres" dp="0" 
           x="200" y="100" size="24"/>

<!-- Heart rate -->
<component type="metric" metric="hr" dp="0" 
           x="300" y="50" size="32"/>
```

---

### chart

**Description**: Graph displaying metric history.

**Type**: `chart`

#### XML Attributes

| Attribute | Type | Default | Description |
|----------|------|--------|-------------|
| `x`, `y` | int | - | Position |
| `width`, `height` | int | - | Dimensions |
| `metric` | string | - | Metric to plot |
| `samples` | int | 256 | Number of points |
| `fill` | string | - | Fill color RGB |
| `outline` | string | - | Line color RGB |

#### Example

```xml
<component type="chart" 
           x="100" y="600" 
           width="400" height="100" 
           metric="speed" 
           samples="128" 
           fill="0,255,0,128" 
           outline="0,255,0,255"/>
```

---

### map

**Description**: GPS map with route trace.

**Type**: `map`

#### XML Attributes

| Attribute | Type | Default | Description |
|----------|------|--------|-------------|
| `x`, `y` | int | - | Position |
| `size` | int | 256 | Map size (square) |
| `zoom` | int | 15 | Zoom level |
| `corner` | int | - | Rounded corners (px) |
| `rotation` | string | "fixed" | "fixed" or "moving" |

#### Examples

```xml
<!-- Simple map -->
<component type="map" 
           x="50" y="50" 
           size="300" 
           zoom="16"/>

<!-- Rotating map with rounded corners -->
<component type="map" 
           x="1600" y="50" 
           size="400" 
           zoom="15" 
           rotation="moving" 
           corner="20"/>
```

---

### msi/msi2

**Description**: Motor Speed Indicator - Circular speed gauge (car dashboard style).

**Type**: `msi` or `msi2`

#### XML Attributes

| Attribute | Type | Default | Description |
|----------|------|--------|-------------|
| `x`, `y` | int | - | Center position |
| `metric` | string | "speed" | Metric to display |
| `units` | string | "kph" | Units |
| `size` | int | 180 | Diameter |
| `start`, `end` | int | - | Value range |
| `yellow`, `green` | int | - | Color thresholds |
| `needle` | int | 1 | Show needle |
| `textsize` | int | 16 | Central text size |

#### Example

```xml
<component type="msi" 
           x="960" y="540" 
           metric="speed" 
           units="kph" 
           size="200" 
           start="0" 
           end="200" 
           yellow="150" 
           green="100" 
           needle="1"
           textsize="16"/>
```

---

## Layout Components

### composite

Groups multiple widgets at a relative position.

```xml
<composite x="100" y="100" name="speed_block">
    <component type="metric" metric="speed" x="0" y="0" size="48"/>
    <component type="text" x="0" y="50" size="16">km/h</component>
</composite>
```

### translate

Shifts a group of widgets.

```xml
<translate x="1720" y="780">
    <component type="msi" x="0" y="0" size="180"/>
</translate>
```

### frame

Decorative frame with background and border.

```xml
<frame x="50" y="50" width="300" height="100" 
       bg="0,0,0,180" 
       outline="255,255,255,100" 
       cr="10"/>
```

---

## Complete Configuration : Karting Layout

Complete karting layout example:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<layout>
    <!-- Speed + gauge block -->
    <composite x="1720" y="780" name="speed_rpm_block">
        <!-- Speed gauge -->
        <component type="msi" metric="speed" units="kph" 
                   x="0" y="0" size="180" 
                   end="120" yellow="100" green="80" needle="1"/>
        
        <!-- Speed number -->
        <component type="metric" metric="speed" units="kph" dp="0" 
                   x="90" y="140" size="40" align="centre"/>
        
        <!-- Gear -->
        <component type="custom_calc" 
                   expression="f'{int(gear)}' if gear > 0 else 'N'" 
                   x="90" y="45" size="30" align="centre"/>
        
        <!-- RPM bar -->
        <component type="rpm_bar" 
                   x="0" y="200" 
                   width="300" height="50" 
                   segments="24" max_rpm="15000"/>
    </composite>

    <!-- G-Force -->
    <component type="gforce" 
               x="1600" y="50" 
               size="300" max_g="2.5"/>

    <!-- Chronometer -->
    <component type="lap_chronometer" 
               x="800" y="50" 
               width="280" height="100" size="20"/>

    <!-- Lap times table -->
    <component type="lap_times_table" 
               x="30" y="300" 
               width="280" max_laps="8" size="18"/>

    <!-- GPS map -->
    <component type="map" 
               x="50" y="700" 
               size="300" zoom="17" corner="10"/>

    <!-- Session info -->
    <component type="custom_calc" 
               expression="f'Max: {precalc.get(\"max_speed\", 0):.0f} km/h'" 
               x="1000" y="1000" size="20"/>
</layout>
```

---

## Python Functions

### math Module
```python
math.sqrt(x)      # Square root
math.pow(x, y)    # Power
math.floor(x)     # Floor
math.ceil(x)      # Ceiling
```

### Formatting Functions
```python
format_speed(120.5)     # → "120 km/h"
format_temp(78.3)       # → "78°C"
format_rpm(12450)       # → "12450 RPM"
format_g(2.34)          # → "2.3g"
format_laptime(41.045)  # → "0:41.045"
```

### Conditional Operators
```python
# Ternary
result = "Fast" if speed > 100 else "Slow"

# Default value
value = laptime if laptime else 0

# Dictionary get with default
max_speed = precalc.get('max_speed', 0)
```

---

## Tips & Best Practices

### 1. Layout Organization
- Use `<composite>` to group related widgets
- Name your composites (`name="speed_block"`) for easier maintenance

### 2. Performance
- Limit visible widgets simultaneously
- Use reasonable `max_laps` for `lap_times_table` (8-10 max)
- Charts (`chart`) with too many `samples` can slow down

### 3. Readability
- Always add black `stroke` (outline) on white text
- Use semi-transparent backgrounds: `bg="0,0,0,180"`
- Consistent spacing: multiples of 10 or 20px

### 4. Resolutions
- **1080p**: 16-24px for text, 180-200px for gauges
- **4K**: Double all values
- Test on target resolution!

### 5. Karting Data
- `rpm` is mapped to `cad` in GPX
- Calculated `gear` is stored in `calculated_gear`
- Laps: `lap`, `laptime`, `laptype` are available

---

## Troubleshooting

### Widget not displaying
1. Check type is correct: `type="rpm_bar"`
2. Check coordinates: are they within video frame?
3. Add debug prints in widget

### "attribute not found" error
- Ensure attribute exists in `@allow_attributes`
- Check factory in `layout_xml.py`

### Incorrect values
- Check mapping in GPX (rpm → cad, etc.)
- Use `custom_calc` with prints to debug

### Slow performance
- Reduce `segments` in `rpm_bar`
- Reduce `max_laps` in `lap_times_table`
- Disable unused features

---

## Complete Layout Examples

See files:
- `layout_karting_1080.xml` - Karting configuration 1080p
- `layout_paragliding_1080.xml` - Paragliding configuration
- `examples/layout/` - Official examples

---

**Version**: 1.0.0  
**Date**: December 31, 2025  
**Author**: Vincent Capicotto (@capic2)  
**Project**: [github.com/capic2/gopro-dashboard-overlay](https://github.com/capic2/gopro-dashboard-overlay)
