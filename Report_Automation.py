# ==========================
# Lead Analysis PDF Generator - Box Plots & Z-score Maps (High/Moderate/Low)
# ==========================
import os
os.environ["OMP_NUM_THREADS"] = "1"

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.patches as mpatches
from shapely.geometry import Point
import matplotlib.patheffects as path_effects

# --------------------------
# 1. USER CONFIGURATION
# --------------------------
GDB_PATH = r"C:\Users\halza\OneDrive\Documents\ArcGIS\Projects\Yorkshire Project\Yorkshire Project.gdb"
OUTPUT_FOLDER = r"C:\Users\halza\OneDrive\Documents\ArcGIS\Projects\Yorkshire Project\Reports"
PDF_TITLE = "Lead (Pb) in River Aire – Annual Distribution & Spatial Patterns"
PDF_FILENAME = "Lead_Pb_River_Aire_BoxPlots_and_ZScoreMaps.pdf"

SAMPLES_LAYER = "lead_samples"
CATCHMENTS_LAYER = "WFD_Catchments"
MAP_CATCHMENTS_LAYER = "Catchment_Samples"
MAP_RIVERS_LAYER = "River_Samples"

CATCHMENT_NAMES = ["Aire Upper", "Aire Middle", "Aire Lower"]
BOX_PLOT_TITLE = "Annual Distribution of Lead Concentrations (99th percentile filter applied)"
SPATIAL_MAP_TITLE = "Spatial Distribution of Standardised Lead (z-score)"
DETERMINAND = "Pb"
UNITS = "µg/L"
Y_MIN, Y_MAX = 0, 80
PAGE_WIDTH, PAGE_HEIGHT = 11.7, 8.3

# --------------------------
# 2. LOAD DATA
# --------------------------
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

gdf_samples = gpd.read_file(GDB_PATH, layer=SAMPLES_LAYER)
gdf_catchments = gpd.read_file(GDB_PATH, layer=CATCHMENTS_LAYER)
gdf_map_catchments = gpd.read_file(GDB_PATH, layer=MAP_CATCHMENTS_LAYER)
gdf_map_rivers = gpd.read_file(GDB_PATH, layer=MAP_RIVERS_LAYER)

gdf_samples["sample_sampleDateTime"] = pd.to_datetime(gdf_samples["sample_sampleDateTime"])
gdf_samples["Year"] = gdf_samples["sample_sampleDateTime"].dt.year

for df in [gdf_map_catchments, gdf_map_rivers]:
    df['z_score'] = pd.to_numeric(df['z_score'], errors='coerce')

# --------------------------
# 3. HELPER FUNCTION
# --------------------------
def classify_z(z):
    if pd.isna(z):
        return 'No Data'
    elif z > 1:
        return 'High'
    elif z < -1:
        return 'Low'
    else:
        return 'Moderate'

z_colors = {'Low':'#1f78b4', 'Moderate':'#b2df8a', 'High':'#e31a1c', 'No Data':'#b0b0b0'}

gdf_map_catchments['z_class'] = gdf_map_catchments['z_score'].apply(classify_z)
gdf_map_rivers['z_class'] = gdf_map_rivers['z_score'].apply(classify_z)

# --------------------------
# 4. CREATE FIGURE
# --------------------------
fig = plt.figure(figsize=(PAGE_WIDTH, PAGE_HEIGHT))

# Left Panel: Box Plots per Year
left_axes = [fig.add_subplot(3, 2, i) for i in [1, 3, 5]]
for ax, cname in zip(left_axes, CATCHMENT_NAMES):
    catch_geom = gdf_catchments[gdf_catchments["OPCAT_NAME"] == cname].geometry.unary_union
    gdf_catch = gdf_samples[gdf_samples.geometry.within(catch_geom)]
    
    # Filter 99th percentile
    gdf_catch = gdf_catch[gdf_catch["result"] <= gdf_catch["result"].quantile(0.99)]
    
    # Prepare data per year
    years_sorted = sorted(gdf_catch["Year"].unique())
    data_per_year = [gdf_catch[gdf_catch["Year"]==year]["result"].values for year in years_sorted]
    
    # Box plot
    ax.boxplot(data_per_year, labels=years_sorted, patch_artist=True,
               boxprops=dict(facecolor='#a6cee3', color='black'),
               medianprops=dict(color='red'))
    
    ax.set_ylim(Y_MIN, Y_MAX)
    ax.set_ylabel(f"{DETERMINAND} ({UNITS})", fontsize=9)
    ax.set_title(cname, fontsize=10, fontstyle='italic')
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.tick_params(axis='y', labelsize=8)
    ax.tick_params(axis='x', labelsize=8, rotation=45)

# Left panel title
fig.text(0.05, 0.93, BOX_PLOT_TITLE, fontsize=12, fontweight='bold', ha='left', va='top')

# Right Panel: Map
ax_map = fig.add_subplot(1, 2, 2)

# Plot catchments
for cls, color in z_colors.items():
    subset = gdf_map_catchments[gdf_map_catchments['z_class']==cls]
    if not subset.empty:
        subset.plot(ax=ax_map, color=color, edgecolor='black')

# Plot rivers
for cls, color in z_colors.items():
    subset = gdf_map_rivers[gdf_map_rivers['z_class']==cls]
    if not subset.empty:
        subset.plot(ax=ax_map, color=color, linewidth=2)

# Catchment labels with arrows and halo
label_offset = 0.01
placed_labels = []
for name, group in gdf_map_catchments.groupby('OPCAT_NAME'):
    geom = group.unary_union
    if geom is None:
        continue
    x_cent, y_cent = geom.centroid.coords[0]
    minx, miny, maxx, maxy = geom.bounds
    width, height = maxx - minx, maxy - miny

    for dx, dy in [(0,height*label_offset),(0,-height*label_offset),(-width*label_offset,0),(width*label_offset,0)]:
        x_label, y_label = x_cent+dx, y_cent+dy
        pt = Point(x_label, y_label)
        if not (pt.within(gdf_map_catchments.unary_union) or any(pt.distance(l)<0.005 for l in placed_labels)):
            break
    else:
        x_label, y_label = x_cent, y_cent + height*label_offset

    txt = ax_map.text(x_label, y_label, name, fontsize=7, ha='center', va='bottom', fontweight='bold', color='black')
    txt.set_path_effects([path_effects.Stroke(linewidth=2, foreground='white'), path_effects.Normal()])
    placed_labels.append(Point(x_label, y_label))

    ax_map.annotate("", xy=(x_cent, y_cent), xytext=(x_label, y_label), arrowprops=dict(arrowstyle='-', color='black', lw=0.5))

ax_map.set_title(SPATIAL_MAP_TITLE, fontsize=12, fontstyle='italic')
ax_map.axis('off')

# Legend
catch_handles = [mpatches.Patch(color=z_colors[k], label=k) for k in ['Low','Moderate','High','No Data']]
ax_map.add_artist(ax_map.legend(handles=catch_handles, title="Catchments & Rivers (z-score)", loc='upper center', bbox_to_anchor=(0.5, -0.1), ncol=2))

# Final layout and save PDF
fig.suptitle(PDF_TITLE, fontsize=16, fontweight='bold')
plt.tight_layout(rect=[0,0.05,1,0.93])
with PdfPages(os.path.join(OUTPUT_FOLDER, PDF_FILENAME)) as pdf:
    pdf.savefig(fig)
    plt.close(fig)

print(f"✅ Integrated PDF created: {os.path.join(OUTPUT_FOLDER, PDF_FILENAME)}")

# ==========================
# Lead Analysis PDF Generator - Line Graphs & Z-score Maps
# ==========================
import os
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.patches as mpatches
from shapely.geometry import Point
import matplotlib.patheffects as path_effects

# --------------------------
# 1. USER CONFIGURATION
# --------------------------
GDB_PATH = r"C:\Users\halza\OneDrive\Documents\ArcGIS\Projects\Yorkshire Project\Yorkshire Project.gdb"
OUTPUT_FOLDER = r"C:\Users\halza\OneDrive\Documents\ArcGIS\Projects\Yorkshire Project\Reports"
PDF_TITLE = "Lead (Pb) in River Aire – Mean Concentrations & Spatial Patterns"
PDF_FILENAME = "Lead_Pb_River_Aire_LineGraphs_and_ZScoreMaps.pdf"

MAP_CATCHMENTS_LAYER = "Catchment_Samples"
MAP_RIVERS_LAYER = "River_Samples"

SPATIAL_MAP_TITLE = "Spatial Distribution of Standardised Lead (z-score)"
Y_MIN, Y_MAX = 0, 80
PAGE_WIDTH, PAGE_HEIGHT = 11.7, 8.3

# --------------------------
# 2. LOAD DATA
# --------------------------
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

gdf_map_catchments = gpd.read_file(GDB_PATH, layer=MAP_CATCHMENTS_LAYER)
gdf_map_rivers = gpd.read_file(GDB_PATH, layer=MAP_RIVERS_LAYER)

# Ensure numeric z_scores
for df in [gdf_map_catchments, gdf_map_rivers]:
    df['z_score'] = pd.to_numeric(df['z_score'], errors='coerce')

# --------------------------
# 3. Z-SCORE CLASSIFICATION
# --------------------------
def classify_z(z):
    if pd.isna(z):
        return 'No Data'
    elif z > 1:
        return 'High'
    elif z < -1:
        return 'Low'
    else:
        return 'Moderate'

z_colors = {'Low':'#1f78b4', 'Moderate':'#b2df8a', 'High':'#e31a1c', 'No Data':'#b0b0b0'}
gdf_map_catchments['z_class'] = gdf_map_catchments['z_score'].apply(classify_z)
gdf_map_rivers['z_class'] = gdf_map_rivers['z_score'].apply(classify_z)

# --------------------------
# 4. CREATE FIGURE
# --------------------------
fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(PAGE_WIDTH, PAGE_HEIGHT), gridspec_kw={'width_ratios':[1,1]})

# Left panel: Line graphs of MEAN_result by OPCAT_NAME
ax_line = axes[0]

for name, group in gdf_map_catchments.groupby('OPCAT_NAME'):
    if 'Year' not in group.columns:
        continue
    # Sort by Year
    group_sorted = group.sort_values('Year')
    ax_line.plot(group_sorted['Year'], group_sorted['MEAN_result'], marker='o', label=name)

ax_line.set_xlabel('Year', fontsize=10)
ax_line.set_ylabel('Mean Pb (µg/L)', fontsize=10)
ax_line.set_title('Mean Lead Concentrations by Catchment', fontsize=12, fontweight='bold')
ax_line.set_ylim(Y_MIN, Y_MAX)
ax_line.grid(True, linestyle='--', alpha=0.5)
ax_line.legend(fontsize=8)

# Right panel: Map
ax_map = axes[1]

# Plot catchments
for cls, color in z_colors.items():
    subset = gdf_map_catchments[gdf_map_catchments['z_class']==cls]
    if not subset.empty:
        subset.plot(ax=ax_map, color=color, edgecolor='black')

# Plot rivers
for cls, color in z_colors.items():
    subset = gdf_map_rivers[gdf_map_rivers['z_class']==cls]
    if not subset.empty:
        subset.plot(ax=ax_map, color=color, linewidth=2)

# Catchment labels with halo
label_offset = 0.01
placed_labels = []
for name, group in gdf_map_catchments.groupby('OPCAT_NAME'):
    geom = group.unary_union
    if geom is None:
        continue
    x_cent, y_cent = geom.centroid.coords[0]
    minx, miny, maxx, maxy = geom.bounds
    width, height = maxx - minx, maxy - miny

    for dx, dy in [(0,height*label_offset),(0,-height*label_offset),(-width*label_offset,0),(width*label_offset,0)]:
        x_label, y_label = x_cent+dx, y_cent+dy
        pt = Point(x_label, y_label)
        if not (pt.within(gdf_map_catchments.unary_union) or any(pt.distance(l)<0.005 for l in placed_labels)):
            break
    else:
        x_label, y_label = x_cent, y_cent + height*label_offset

    txt = ax_map.text(x_label, y_label, name, fontsize=7, ha='center', va='bottom', fontweight='bold', color='black')
    txt.set_path_effects([path_effects.Stroke(linewidth=2, foreground='white'), path_effects.Normal()])
    placed_labels.append(Point(x_label, y_label))
    ax_map.annotate("", xy=(x_cent, y_cent), xytext=(x_label, y_label), arrowprops=dict(arrowstyle='-', color='black', lw=0.5))

ax_map.set_title(SPATIAL_MAP_TITLE, fontsize=12, fontstyle='italic')
ax_map.axis('off')

# Legend
catch_handles = [mpatches.Patch(color=z_colors[k], label=k) for k in ['Low','Moderate','High','No Data']]
ax_map.add_artist(ax_map.legend(handles=catch_handles, title="Catchments & Rivers (z-score)", loc='upper center', bbox_to_anchor=(0.5, -0.05), ncol=2))

# Final layout and save PDF
fig.suptitle(PDF_TITLE, fontsize=16, fontweight='bold')
plt.tight_layout(rect=[0,0.05,1,0.93])
with PdfPages(os.path.join(OUTPUT_FOLDER, PDF_FILENAME)) as pdf:
    pdf.savefig(fig)
    plt.close(fig)

print(f"✅ Integrated PDF created: {os.path.join(OUTPUT_FOLDER, PDF_FILENAME)}")


# ==========================
# Lead Analysis PDF Generator - Line Graphs & Z-score Maps
# ==========================
import os
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.patches as mpatches
import matplotlib.patheffects as path_effects

# --------------------------
# 1. USER CONFIGURATION
# --------------------------
GDB_PATH = r"C:\Users\halza\OneDrive\Documents\ArcGIS\Projects\Yorkshire Project\Yorkshire Project.gdb"
OUTPUT_FOLDER = r"C:\Users\halza\OneDrive\Documents\ArcGIS\Projects\Yorkshire Project\Reports"
PDF_TITLE = "Lead (Pb) in River Aire – Monitoring Trends & Spatial Patterns"
PDF_FILENAME = "Lead_Pb_River_Aire_LineGraphs_and_ZScoreMaps.pdf"

SAMPLES_LAYER = "lead_samples"
CATCHMENTS_LAYER = "WFD_Catchments"
MAP_CATCHMENTS_LAYER = "Catchment_Samples"
MAP_RIVERS_LAYER = "River_Samples"

CATCHMENTS_OF_INTEREST = [
    "Colne and Holme", "Aire Lower", "Calder Lower",
    "Aire Middle", "Calder Middle", "Aire Upper", "Calder Upper"
]

SPATIAL_MAP_TITLE = "Spatial Distribution of Standardised Lead (z-score)"
Y_MIN, Y_MAX = 0, 80
PAGE_WIDTH, PAGE_HEIGHT = 11.7, 8.3

# --------------------------
# 2. LOAD DATA
# --------------------------
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

gdf_samples = gpd.read_file(GDB_PATH, layer=SAMPLES_LAYER)
gdf_catchments = gpd.read_file(GDB_PATH, layer=CATCHMENTS_LAYER)
gdf_map_catchments = gpd.read_file(GDB_PATH, layer=MAP_CATCHMENTS_LAYER)
gdf_map_rivers = gpd.read_file(GDB_PATH, layer=MAP_RIVERS_LAYER)

# Clean column names
gdf_samples.columns = gdf_samples.columns.str.strip()
gdf_catchments.columns = gdf_catchments.columns.str.strip()

# Convert sample datetime to year
gdf_samples['sample_sampleDateTime'] = pd.to_datetime(gdf_samples['sample_sampleDateTime'])
gdf_samples['Year'] = gdf_samples['sample_sampleDateTime'].dt.year

# --------------------------
# 3. SPATIAL JOIN SAMPLES TO CATCHMENTS
# --------------------------
# Ensure same CRS
if gdf_samples.crs != gdf_catchments.crs:
    gdf_samples = gdf_samples.to_crs(gdf_catchments.crs)

# Spatial join
gdf_samples_joined = gpd.sjoin(
    gdf_samples, 
    gdf_catchments[['OPCAT_NAME', 'geometry']], 
    how='inner', 
    predicate='within'
)

# Filter to selected catchments
gdf_samples_filtered = gdf_samples_joined[gdf_samples_joined['OPCAT_NAME'].isin(CATCHMENTS_OF_INTEREST)].copy()

# --------------------------
# 4. CLASSIFY Z-SCORES FOR MAPS
# --------------------------
def classify_z(z):
    if pd.isna(z):
        return 'No Data'
    elif z > 1:
        return 'High'
    elif z < -1:
        return 'Low'
    else:
        return 'Moderate'

z_colors = {'Low':'#1f78b4', 'Moderate':'#b2df8a', 'High':'#e31a1c', 'No Data':'#b0b0b0'}

for df in [gdf_map_catchments, gdf_map_rivers]:
    df['z_score'] = pd.to_numeric(df['z_score'], errors='coerce')
    df['z_class'] = df['z_score'].apply(classify_z)

# --------------------------
# 5. CREATE FIGURE
# --------------------------
fig, axes = plt.subplots(nrows=len(CATCHMENTS_OF_INTEREST), ncols=1, figsize=(8, PAGE_HEIGHT), sharex=True)

if len(CATCHMENTS_OF_INTEREST) == 1:
    axes = [axes]

for ax, catch in zip(axes, CATCHMENTS_OF_INTEREST):
    gdf_c = gdf_samples_filtered[gdf_samples_filtered['OPCAT_NAME'] == catch]
    if gdf_c.empty:
        continue
    # Aggregate mean per year
    mean_per_year = gdf_c.groupby('Year')['result'].mean().reset_index()
    
    ax.plot(mean_per_year['Year'], mean_per_year['result'], marker='o', linestyle='-', label=catch)
    ax.set_ylabel("Pb (µg/L)")
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.set_title(catch, fontsize=10, fontstyle='italic')

axes[-1].set_xlabel("Year")

# Add line graph title
fig.suptitle("Mean Lead Concentrations Over Time by Catchment", fontsize=14, fontweight='bold')

# --------------------------
# 6. ADD MAP PANEL
# --------------------------
fig_map, ax_map = plt.subplots(figsize=(PAGE_WIDTH, PAGE_HEIGHT/2))

for cls, color in z_colors.items():
    subset = gdf_map_catchments[gdf_map_catchments['z_class']==cls]
    if not subset.empty:
        subset.plot(ax=ax_map, color=color, edgecolor='black')
for cls, color in z_colors.items():
    subset = gdf_map_rivers[gdf_map_rivers['z_class']==cls]
    if not subset.empty:
        subset.plot(ax=ax_map, color=color, linewidth=2)

ax_map.set_title(SPATIAL_MAP_TITLE, fontsize=12, fontstyle='italic')
ax_map.axis('off')

catch_handles = [mpatches.Patch(color=z_colors[k], label=k) for k in z_colors]
ax_map.add_artist(ax_map.legend(handles=catch_handles, title="Catchments & Rivers (z-score)", loc='upper center', bbox_to_anchor=(0.5, -0.1), ncol=2))

# --------------------------
# 7. SAVE TO PDF
# --------------------------
pdf_path = os.path.join(OUTPUT_FOLDER, PDF_FILENAME)
with PdfPages(pdf_path) as pdf:
    pdf.savefig(fig)
    pdf.savefig(fig_map)
    plt.close('all')

print(f"✅ PDF created: {pdf_path}")

import os
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

# --------------------------
# CONFIGURATION
# --------------------------
GDB_PATH = r"C:\Users\halza\OneDrive\Documents\ArcGIS\Projects\Yorkshire Project\Yorkshire Project.gdb"
OUTPUT_FOLDER = r"C:\Users\halza\OneDrive\Documents\ArcGIS\Projects\Yorkshire Project\Reports"
PDF_FILENAME = "Lead_Pb_LineGraphs.pdf"

SAMPLES_LAYER = "lead_samples"
CATCHMENTS_LAYER = "WFD_Catchments"

CATCHMENTS_OF_INTEREST = [
    "Colne and Holme", "Aire Lower", "Calder Lower",
    "Aire Middle", "Calder Middle", "Aire Upper", "Calder Upper"
]

PAGE_WIDTH, PAGE_HEIGHT = 8, 12  # Tall figure for stacked plots
Y_MIN, Y_MAX = 0, 80

# --------------------------
# LOAD DATA
# --------------------------
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

gdf_samples = gpd.read_file(GDB_PATH, layer=SAMPLES_LAYER)
gdf_catchments = gpd.read_file(GDB_PATH, layer=CATCHMENTS_LAYER)

# Clean column names
gdf_samples.columns = gdf_samples.columns.str.strip()
gdf_catchments.columns = gdf_catchments.columns.str.strip()

# Convert sample datetime to year
gdf_samples['sample_sampleDateTime'] = pd.to_datetime(gdf_samples['sample_sampleDateTime'])
gdf_samples['Year'] = gdf_samples['sample_sampleDateTime'].dt.year

# --------------------------
# SPATIAL JOIN: Assign OPCAT_NAME to samples
# --------------------------
if gdf_samples.crs != gdf_catchments.crs:
    gdf_samples = gdf_samples.to_crs(gdf_catchments.crs)

gdf_samples_joined = gpd.sjoin(
    gdf_samples, 
    gdf_catchments[['OPCAT_NAME', 'geometry']], 
    how='inner', 
    predicate='within'
)

# Filter only selected catchments
gdf_samples_filtered = gdf_samples_joined[gdf_samples_joined['OPCAT_NAME'].isin(CATCHMENTS_OF_INTEREST)].copy()

# --------------------------
# CREATE STACKED LINE GRAPHS
# --------------------------
fig, axes = plt.subplots(
    nrows=len(CATCHMENTS_OF_INTEREST), ncols=1,
    figsize=(PAGE_WIDTH, PAGE_HEIGHT),
    sharex=True
)

# Ensure axes is a list
if len(CATCHMENTS_OF_INTEREST) == 1:
    axes = [axes]

for ax, catch in zip(axes, CATCHMENTS_OF_INTEREST):
    gdf_c = gdf_samples_filtered[gdf_samples_filtered['OPCAT_NAME'] == catch]
    if gdf_c.empty:
        continue
    # Aggregate mean per year
    mean_per_year = gdf_c.groupby('Year')['result'].mean().reset_index()
    
    # Plot black line
    ax.plot(mean_per_year['Year'], mean_per_year['result'], color='black', marker='o', linestyle='-')
    ax.set_ylabel("Pb (µg/L)", fontsize=9)
    ax.set_ylim(Y_MIN, Y_MAX)
    ax.set_title(catch, fontsize=10, fontstyle='italic')
    ax.grid(True, linestyle='--', alpha=0.5)

# Shared X-axis label
axes[-1].set_xlabel("Year", fontsize=10)

# Adjust layout to avoid overlaps
plt.tight_layout(h_pad=1.0)
fig.suptitle("Mean Lead Concentrations Over Time by Catchment", fontsize=14, fontweight='bold', y=1.02)

# --------------------------
# SAVE TO PDF
# --------------------------
pdf_path = os.path.join(OUTPUT_FOLDER, PDF_FILENAME)
from matplotlib.backends.backend_pdf import PdfPages
with PdfPages(pdf_path) as pdf:
    pdf.savefig(fig)
    plt.close(fig)

print(f"✅ Line graph PDF created: {pdf_path}")

# ==========================
# Lead (Pb) Map Report – Mean Results (improved labels & legend)
# ==========================
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import ListedColormap, BoundaryNorm
import mapclassify
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from shapely.geometry import Point
import matplotlib.patheffects as path_effects

# --------------------------
# 1. USER CONFIGURATION
# --------------------------
GDB_PATH = r"C:\Users\halza\OneDrive\Documents\ArcGIS\Projects\Yorkshire Project\Yorkshire Project.gdb"
OUTPUT_FOLDER = r"C:\Users\halza\OneDrive\Documents\ArcGIS\Projects\Yorkshire Project\Reports"
PDF_TITLE = "Lead (Pb) in Rivers and Catchments — Spatial Distribution (Mean Results)"
PDF_FILENAME = "Lead_Pb_Spatial_Distribution_MEAN_optimized.pdf"

CATCHMENTS_LAYER = "WFD_Catchments"
MAP_CATCHMENTS_LAYER = "Catchment_Samples"
MAP_RIVERS_LAYER = "River_Samples"

DETERMINAND = "Pb"
UNITS = "µg/L"
PAGE_WIDTH, PAGE_HEIGHT = 11.7, 8.3

# --------------------------
# 2. LOAD DATA
# --------------------------
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

gdf_catchments = gpd.read_file(GDB_PATH, layer=CATCHMENTS_LAYER)
gdf_map_catchments = gpd.read_file(GDB_PATH, layer=MAP_CATCHMENTS_LAYER)
gdf_map_rivers = gpd.read_file(GDB_PATH, layer=MAP_RIVERS_LAYER)

# Ensure MEAN_result is numeric
for df in [gdf_map_catchments, gdf_map_rivers]:
    df['MEAN_result'] = pd.to_numeric(df.get('MEAN_result'), errors='coerce')

# Quick diagnostics (optional)
print("Catchment MEAN_result value counts (including NaN):")
print(gdf_map_catchments['MEAN_result'].isna().value_counts(dropna=False))
print("River MEAN_result value counts (including NaN):")
print(gdf_map_rivers['MEAN_result'].isna().value_counts(dropna=False))

# --------------------------
# 3. CLASSIFICATION (robust)
# --------------------------
def get_class_boundaries(values, k=3):
    """
    Return class boundaries (length k+1) for values.
    Prefer NaturalBreaks, fall back to quantiles, handle small/empty sets.
    """
    vals = values.dropna()
    if vals.empty:
        return None  # nothing to classify
    try:
        # Try Natural Breaks first
        nb = mapclassify.NaturalBreaks(vals, k=k)
        # nb.bins are the class upper bounds; create boundaries including the min
        lower = float(vals.min())
        boundaries = [lower] + list(nb.bins)
        # Ensure we have exactly k+1 boundaries; if not, fallback:
        if len(boundaries) != k + 1:
            raise ValueError("Unexpected nb.bins length")
    except Exception:
        # Fallback: equal-sized quantiles (0, 1/k, 2/k, ..., 1)
        qs = vals.quantile([i / k for i in range(k + 1)]).values
        boundaries = list(np.round(qs.astype(float), 12))
    # If boundaries contain duplicates (e.g., low variance), compress them gracefully
    # Ensure strictly non-decreasing and enlarge tiny ranges
    boundaries = list(boundaries)
    for i in range(1, len(boundaries)):
        if boundaries[i] <= boundaries[i - 1]:
            boundaries[i] = boundaries[i - 1] + 1e-9
    return boundaries

def build_norm_and_cmap(values, colors):
    """
    Build BoundaryNorm and ListedColormap based on values and given colors.
    Returns (boundaries, cmap, norm).
    """
    boundaries = get_class_boundaries(values, k=len(colors))
    if boundaries is None:
        # no data: return fallback single bin covering [0,1]
        boundaries = [0.0, 1.0]
        cmap = ListedColormap([colors[0]])
        norm = BoundaryNorm(boundaries, ncolors=1, clip=True)
        return boundaries, cmap, norm
    # For BoundaryNorm we need boundaries length == ncolors + 1
    cmap = ListedColormap(colors[:len(boundaries)-1])
    norm = BoundaryNorm(boundaries, ncolors=len(boundaries)-1, clip=True)
    return boundaries, cmap, norm

# Your colour schemes (same as before)
catch_colors = ['#a6cee3', '#7fb3d5', '#6a3d9a']
river_colors = ['#fdbf6f', '#fb8072', '#b22222']

catch_boundaries, cmap_catch, norm_catch = build_norm_and_cmap(gdf_map_catchments['MEAN_result'], catch_colors)
river_boundaries, cmap_river, norm_river = build_norm_and_cmap(gdf_map_rivers['MEAN_result'], river_colors)

# --------------------------
# 4. PLOT MAP (improved)
# --------------------------
fig, ax_map = plt.subplots(figsize=(PAGE_WIDTH, PAGE_HEIGHT))

# Plot catchments (fill)
if gdf_map_catchments['MEAN_result'].dropna().shape[0] > 0:
    gdf_map_catchments.plot(column='MEAN_result', cmap=cmap_catch, norm=norm_catch,
                            edgecolor='black', ax=ax_map,
                            missing_kwds={"color":"#b0b0b0", "edgecolor":"black"})
else:
    # no numeric catchment data
    gdf_map_catchments.plot(ax=ax_map, color="#b0b0b0", edgecolor='black')

# Plot rivers (lines)
if gdf_map_rivers['MEAN_result'].dropna().shape[0] > 0:
    gdf_map_rivers.plot(column='MEAN_result', cmap=cmap_river, norm=norm_river,
                        linewidth=2, ax=ax_map,
                        missing_kwds={"color":"#b0b0b0"})
else:
    gdf_map_rivers.plot(ax=ax_map, color="#b0b0b0", linewidth=2)

# Title (main)
fig.suptitle(PDF_TITLE, fontsize=14, fontweight='bold')

# Improve label placement for catchments:
label_offset_frac = 0.12  # how far from centroid to try offsets relative to bbox
placed_points = []  # list of (x, y) of placed labels, for simple collision avoidance

for name, group in gdf_map_catchments.groupby('OPCAT_NAME'):
    if group.geometry.is_empty.all():
        continue
    geom = group.unary_union
    # representative_point() is guaranteed inside polygon (better than centroid for odd shapes)
    try:
        rpt = geom.representative_point()
    except Exception:
        # fallback to centroid
        rpt = geom.centroid
    x_cent, y_cent = rpt.x, rpt.y
    minx, miny, maxx, maxy = geom.bounds
    width, height = maxx - minx if maxx - minx > 0 else 1.0, maxy - miny if maxy - miny > 0 else 1.0
    # Try a few offsets to avoid overlaps
    offsets = [
        (0, height * label_offset_frac),
        (0, -height * label_offset_frac),
        (-width * label_offset_frac, 0),
        (width * label_offset_frac, 0),
        (width * label_offset_frac, height * label_offset_frac),
        (-width * label_offset_frac, height * label_offset_frac),
        (-width * label_offset_frac, -height * label_offset_frac),
        (width * label_offset_frac, -height * label_offset_frac),
        (0, 0)
    ]
    chosen = None
    threshold = max(width, height) * 0.18
    for dx, dy in offsets:
        lx, ly = x_cent + dx, y_cent + dy
        lp = Point(lx, ly)
        # check roughly if too close to other labels
        if not any(lp.distance(Point(px, py)) < threshold for px, py in placed_points):
            chosen = (lx, ly)
            break
    if chosen is None:
        chosen = (x_cent, y_cent + height * label_offset_frac)  # last resort

    lx, ly = chosen
    txt = ax_map.text(lx, ly, name, fontsize=7, ha='center', va='center', fontweight='bold', color='black')
    # white halo for readability
    txt.set_path_effects([path_effects.Stroke(linewidth=2.5, foreground='white'), path_effects.Normal()])
    placed_points.append((lx, ly))
    # draw thin connector line to the representative point if label is offset
    if (lx, ly) != (x_cent, y_cent):
        ax_map.annotate("", xy=(x_cent, y_cent), xytext=(lx, ly),
                        arrowprops=dict(arrowstyle='-', color='black', lw=0.4, alpha=0.7))

ax_map.axis('off')

# --------------------------
# 5. LEGEND (top-right, clear labels)
# --------------------------
# Build catchment legend handles with numeric ranges
def build_range_labels(boundaries, unit_label):
    labels = []
    if boundaries is None:
        return ["No data"]
    # boundaries is length n+1 for n classes
    for i in range(len(boundaries) - 1):
        low = boundaries[i]
        high = boundaries[i + 1]
        # Format nicely: if small numbers, show 2 decimals; else show 2 decimals anyway
        labels.append(f"{low:.2f} – {high:.2f} {unit_label}")
    return labels

catch_labels = build_range_labels(catch_boundaries, UNITS) if catch_boundaries is not None else []
river_labels = build_range_labels(river_boundaries, UNITS) if river_boundaries is not None else []

# create patch handles
catch_handles = []
if catch_boundaries is not None:
    for i, clr in enumerate(catch_colors[:len(catch_labels)]):
        catch_handles.append(mpatches.Patch(facecolor=clr, edgecolor='black', label=f"Catchment: {catch_labels[i]}"))
# No data patch
catch_handles.append(mpatches.Patch(facecolor="#b0b0b0", edgecolor='black', label="Catchment: No data"))

# create line handles for rivers
river_handles = []
if river_boundaries is not None:
    for i, clr in enumerate(river_colors[:len(river_labels)]):
        river_handles.append(Line2D([0], [0], color=clr, lw=3, label=f"River: {river_labels[i]}"))
river_handles.append(Line2D([0], [0], color="#b0b0b0", lw=3, label="River: No data"))

# Place two stacked legends at top-right inside axes
# First catchment legend slightly below the top, then river legend below it
if catch_handles:
    leg1 = ax_map.legend(handles=catch_handles, title="Catchments (mean)", loc='upper right',
                         bbox_to_anchor=(0.98, 0.98), fontsize=8, title_fontsize=9, framealpha=0.9)
    ax_map.add_artist(leg1)
if river_handles:
    # Put river legend slightly lower
    leg2 = ax_map.legend(handles=river_handles, title="Rivers (mean)", loc='upper right',
                         bbox_to_anchor=(0.98, 0.78), fontsize=8, title_fontsize=9, framealpha=0.9)
    ax_map.add_artist(leg2)

# Slight layout tuning
plt.tight_layout(rect=[0, 0, 1, 0.96])  # keep room for suptitle

# Save to PDF
outpath = os.path.join(OUTPUT_FOLDER, PDF_FILENAME)
with PdfPages(outpath) as pdf:
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)

print(f"✅ Optimized map PDF created: {outpath}")


# ==========================
# Water Quality Monitoring Report
# ==========================

import os
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import ListedColormap, BoundaryNorm
import matplotlib.patches as mpatches
import matplotlib.patheffects as path_effects
from shapely.geometry import Point
import mapclassify

# --------------------------
# 1. CONFIGURATION
# --------------------------
GDB_PATH = r"C:\Users\halza\OneDrive\Documents\ArcGIS\Projects\Yorkshire Project\Yorkshire Project.gdb"
OUTPUT_FOLDER = r"C:\Users\halza\OneDrive\Documents\ArcGIS\Projects\Yorkshire Project\Reports"
PDF_FILENAME = "Water_Quality_Monitoring_Report.pdf"

# Layers
SAMPLES_LAYER = "lead_samples"
CATCHMENTS_LAYER = "WFD_Catchments"
MAP_CATCHMENTS_LAYER = "Catchment_Samples"
MAP_RIVERS_LAYER = "River_Samples"

# Catchments for line graphs
CATCHMENTS_OF_INTEREST = [
    "Colne and Holme", "Aire Lower", "Calder Lower",
    "Aire Middle", "Calder Middle", "Aire Upper", "Calder Upper"
]

# Figure / page settings
PAGE_WIDTH, PAGE_HEIGHT = 11.7, 8.3  # A4 landscape
Y_MIN, Y_MAX = 0, 80  # y-axis limits for line graphs

# Titles
PDF_TITLE = "Water Quality Monitoring Report"
TIME_SERIES_TITLE = "Mean Lead Concentrations Over Time (2022–2024)"
SPATIAL_MAP_TITLE = "Spatial Distribution of Mean Lead (Pb)\nManagement Catchment: Aire & Calder (2022–2024)"
DETERMINAND = "Pb"
UNITS = "µg/L"

# --------------------------
# 2. LOAD DATA
# --------------------------
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

gdf_samples = gpd.read_file(GDB_PATH, layer=SAMPLES_LAYER)
gdf_catchments = gpd.read_file(GDB_PATH, layer=CATCHMENTS_LAYER)
gdf_map_catchments = gpd.read_file(GDB_PATH, layer=MAP_CATCHMENTS_LAYER)
gdf_map_rivers = gpd.read_file(GDB_PATH, layer=MAP_RIVERS_LAYER)

# Clean column names
for df in [gdf_samples, gdf_catchments]:
    df.columns = df.columns.str.strip()

# Convert datetime → Year
gdf_samples['sample_sampleDateTime'] = pd.to_datetime(gdf_samples['sample_sampleDateTime'])
gdf_samples['Year'] = gdf_samples['sample_sampleDateTime'].dt.year

# Spatial join to attach catchment names to samples
if gdf_samples.crs != gdf_catchments.crs:
    gdf_samples = gdf_samples.to_crs(gdf_catchments.crs)

gdf_samples_joined = gpd.sjoin(
    gdf_samples,
    gdf_catchments[['OPCAT_NAME', 'geometry']],
    how='inner',
    predicate='within'
)

# Filter only selected catchments
gdf_samples_filtered = gdf_samples_joined[
    gdf_samples_joined['OPCAT_NAME'].isin(CATCHMENTS_OF_INTEREST)
].copy()

# Convert mean results to numeric
for df in [gdf_map_catchments, gdf_map_rivers]:
    df['MEAN_result'] = pd.to_numeric(df['MEAN_result'], errors='coerce')

# --------------------------
# 3. HELPER FUNCTION
# --------------------------
def classify_adaptive(values, max_k=3):
    """Adaptive Natural Breaks classifier (up to k classes)."""
    unique_vals = values.nunique()
    k = min(max_k, unique_vals if unique_vals > 1 else 1)
    return mapclassify.NaturalBreaks(values.dropna(), k=k)

# --------------------------
# 4. CREATE FIGURE (LINE GRAPHS + MAP)
# --------------------------
fig = plt.figure(figsize=(PAGE_WIDTH, PAGE_HEIGHT))

# --- LEFT PANEL: Stacked Line Graphs ---
nrows = len(CATCHMENTS_OF_INTEREST)
left_axes = [fig.add_subplot(nrows, 2, 2*i+1) for i in range(nrows)]

for ax, catch in zip(left_axes, CATCHMENTS_OF_INTEREST):
    gdf_c = gdf_samples_filtered[gdf_samples_filtered['OPCAT_NAME'] == catch]
    if gdf_c.empty:
        continue

    # Aggregate mean per year
    mean_per_year = gdf_c.groupby('Year')['result'].mean().reset_index()

    # Plot black line
    ax.plot(mean_per_year['Year'], mean_per_year['result'],
            color='black', marker='o', linestyle='-')
    ax.set_ylabel(f"{DETERMINAND} ({UNITS})", fontsize=8)
    ax.set_ylim(Y_MIN, Y_MAX)
    ax.set_title(catch, fontsize=9, fontstyle='italic')
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.tick_params(axis='y', labelsize=7)
    ax.tick_params(axis='x', labelsize=7)

# Shared X-axis label
left_axes[-1].set_xlabel("Year", fontsize=9)

# Add left panel title
fig.text(0.05, 0.95, TIME_SERIES_TITLE, fontsize=12, fontweight='bold', ha='left', va='top')

# --- RIGHT PANEL: Spatial Map ---
ax_map = fig.add_subplot(1, 2, 2)

# Catchments symbology
catch_colors = ['#a6cee3', '#7fb3d5', '#6a3d9a']
catch_class = classify_adaptive(gdf_map_catchments['MEAN_result'])
catch_bins = catch_class.bins
cmap_catch = ListedColormap(catch_colors)
norm_catch = BoundaryNorm([0] + list(catch_bins), ncolors=len(catch_colors))
gdf_map_catchments.plot(
    column='MEAN_result', cmap=cmap_catch, norm=norm_catch,
    edgecolor='black', ax=ax_map,
    missing_kwds={"color":"#b0b0b0"}
)

# Rivers symbology
river_colors = ['#fdbf6f', '#fb8072', '#b22222']
river_class = classify_adaptive(gdf_map_rivers['MEAN_result'])
river_bins = river_class.bins
cmap_river = ListedColormap(river_colors)
norm_river = BoundaryNorm([0] + list(river_bins), ncolors=len(river_colors))
gdf_map_rivers.plot(
    column='MEAN_result', cmap=cmap_river, norm=norm_river,
    linewidth=2, ax=ax_map,
    missing_kwds={"color":"#b0b0b0"}
)

# Labels for catchments
label_offset = 0.01
for name, group in gdf_map_catchments.groupby('OPCAT_NAME'):
    geom = group.unary_union
    if geom is None:
        continue
    x_cent, y_cent = geom.centroid.coords[0]
    minx, miny, maxx, maxy = geom.bounds
    width, height = maxx - minx, maxy - miny

    x_label, y_label = x_cent, y_cent + height * label_offset
    txt = ax_map.text(
        x_label, y_label, name,
        fontsize=7, ha='center', va='bottom',
        fontweight='bold', color='black'
    )
    txt.set_path_effects([path_effects.Stroke(linewidth=2, foreground='white'),
                          path_effects.Normal()])

# Map title
ax_map.set_title(SPATIAL_MAP_TITLE, fontsize=12, fontweight='bold')
ax_map.axis('off')

# Legends (top-right inside map)
catch_handles = [mpatches.Patch(color=catch_colors[i],
                label=f"Catchments: {0 if i==0 else catch_bins[i-1]:.2f} – {catch_bins[i]:.2f} {UNITS}")
                for i in range(len(catch_bins))]
catch_handles.append(mpatches.Patch(color="#b0b0b0", label="Catchments: No Data"))

river_handles = [mpatches.Patch(color=river_colors[i],
                label=f"Rivers: {0 if i==0 else river_bins[i-1]:.2f} – {river_bins[i]:.2f} {UNITS}")
                for i in range(len(river_bins))]
river_handles.append(mpatches.Patch(color="#b0b0b0", label="Rivers: No Data"))

leg1 = ax_map.legend(handles=catch_handles, loc='upper right', fontsize=7, title="Catchments", title_fontsize=8)
ax_map.add_artist(leg1)
ax_map.legend(handles=river_handles, loc='lower right', fontsize=7, title="Rivers", title_fontsize=8)

# --------------------------
# 5. EXPORT PDF
# --------------------------
fig.suptitle(PDF_TITLE, fontsize=16, fontweight='bold')
plt.tight_layout(rect=[0,0.05,1,0.93])

pdf_path = os.path.join(OUTPUT_FOLDER, PDF_FILENAME)
with PdfPages(pdf_path) as pdf:
    pdf.savefig(fig)
    plt.close(fig)

print(f"✅ Integrated PDF created: {pdf_path}")


import geopandas as gpd
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors

# Paths
gdb_path = r"C:\Users\halza\OneDrive\Documents\ArcGIS\Projects\Yorkshire Project\Yorkshire Project.gdb"
feature_class = "River_Samples"
output_pdf = r"C:\Users\halza\OneDrive\Documents\ArcGIS\Projects\Yorkshire Project\Reports\Water_Samples_Report.pdf"

# Load feature class from File Geodatabase
gdf = gpd.read_file(f"{gdb_path}", layer=feature_class)

# Select important columns and drop rows where MEAN_Result is null
columns = ['WB_NAME', 'sample_samplingPoint_label', 'determinand_label', 'MEAN_Result', 'determinand_unit_label', 'z_score']
df = gdf[columns].dropna(subset=['MEAN_Result'])

# Rename columns
df.columns = ['Water Body', 'Sampling Point', 'Parameter', 'Mean Result', 'Unit', 'Z-Score']

# Round MEAN_Result to 2 decimal places
df['Mean Result'] = df['Mean Result'].round(2)

# Classify based on existing z-score
def classify(z):
    if z > 1:
        return "High"
    elif z < -1:
        return "Low"
    else:
        return "Moderate"

df['Class'] = df['Z-Score'].apply(classify)

# Sort by Z-Score descending (highest first)
df = df.sort_values(by='Z-Score', ascending=False)

# Prepare table for PDF
pdf_data = [df[['Water Body', 'Sampling Point', 'Parameter', 'Mean Result', 'Unit', 'Class']].columns.tolist()] \
           + df[['Water Body', 'Sampling Point', 'Parameter', 'Mean Result', 'Unit', 'Class']].values.tolist()

# Create PDF in landscape
pdf = SimpleDocTemplate(output_pdf, pagesize=landscape(A4))
table = Table(pdf_data, repeatRows=1)

# Table style
style = TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 10),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
])
table.setStyle(style)

# Build PDF
pdf.build([table])

print(f"PDF created at: {output_pdf}")

# ==========================
# Water Quality Monitoring Report (Graphs + Map)
# ==========================

import os
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import ListedColormap, BoundaryNorm
import matplotlib.patches as mpatches
import matplotlib.patheffects as path_effects
import mapclassify
import matplotlib.gridspec as gridspec
import numpy as np

# --------------------------
# 1. CONFIGURATION
# --------------------------
GDB_PATH = r"C:\Users\halza\OneDrive\Documents\ArcGIS\Projects\Yorkshire Project\Yorkshire Project.gdb"
OUTPUT_FOLDER = r"C:\Users\halza\OneDrive\Documents\ArcGIS\Projects\Yorkshire Project\Reports"
PDF_FILENAME = "Water_Quality_Monitoring.pdf"

SAMPLES_LAYER = "lead_samples"
CATCHMENTS_LAYER = "WFD_Catchments"
MAP_CATCHMENTS_LAYER = "Catchment_Samples"
MAP_RIVERS_LAYER = "River_Samples"

CATCHMENTS_OF_INTEREST = [
    "Colne and Holme", "Aire Lower", "Calder Lower",
    "Aire Middle", "Calder Middle", "Aire Upper", "Calder Upper"
]

PAGE_WIDTH, PAGE_HEIGHT = 11.7, 8.3  # A4 landscape
Y_MIN, Y_MAX = 0, 80
PDF_TITLE = "Water Quality Monitoring Report"
TIME_SERIES_TITLE = "Mean Lead Concentrations Over Time (2022–2024)"
SPATIAL_MAP_TITLE = "Spatial Distribution of Mean Lead (Pb)\nManagement Catchment: Aire & Calder (2022–2024)"
DETERMINAND = "Pb"
UNITS = "µg/L"

# --------------------------
# 2. LOAD DATA
# --------------------------
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

gdf_samples = gpd.read_file(GDB_PATH, layer=SAMPLES_LAYER)
gdf_catchments = gpd.read_file(GDB_PATH, layer=CATCHMENTS_LAYER)
gdf_map_catchments = gpd.read_file(GDB_PATH, layer=MAP_CATCHMENTS_LAYER)
gdf_map_rivers = gpd.read_file(GDB_PATH, layer=MAP_RIVERS_LAYER)

for df in [gdf_samples, gdf_catchments]:
    df.columns = df.columns.str.strip()

gdf_samples['sample_sampleDateTime'] = pd.to_datetime(gdf_samples['sample_sampleDateTime'])
gdf_samples['Year'] = gdf_samples['sample_sampleDateTime'].dt.year

if gdf_samples.crs != gdf_catchments.crs:
    gdf_samples = gdf_samples.to_crs(gdf_catchments.crs)

gdf_samples_joined = gpd.sjoin(
    gdf_samples,
    gdf_catchments[['OPCAT_NAME','geometry']],
    how='inner',
    predicate='within'
)

gdf_samples_filtered = gdf_samples_joined[
    gdf_samples_joined['OPCAT_NAME'].isin(CATCHMENTS_OF_INTEREST)
].copy()

for df in [gdf_map_catchments, gdf_map_rivers]:
    df['MEAN_result'] = pd.to_numeric(df['MEAN_result'], errors='coerce')

# --------------------------
# 3. HELPER FUNCTIONS
# --------------------------
def classify_adaptive(values, max_k=3):
    unique_vals = values.nunique()
    k = min(max_k, unique_vals if unique_vals > 1 else 1)
    return mapclassify.NaturalBreaks(values.dropna(), k=k)

def add_north_arrow(ax):
    ax.annotate('N', xy=(0.5, 0.97), xycoords='axes fraction',
                ha='center', va='bottom', fontsize=12, fontweight='bold')
    ax.arrow(0.5, 0.90, 0, 0.05, transform=ax.transAxes,
             head_width=0.02, head_length=0.03, fc='k', ec='k')

def add_scale_bar(ax, total_km=20, segments=4, location=(0.5, 0.05)):
    """
    ArcGIS-style double alternating scale bar.
    total_km: total length of scale bar in km.
    segments: number of alternating segments.
    location: (x,y) in axes fraction.
    """
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    map_width_m = xmax - xmin

    length_m = total_km * 1000
    if length_m > map_width_m:
        length_m = map_width_m * 0.25
        total_km = int(length_m / 1000)

    # Segment length
    seg_len = length_m / segments

    # Anchor position
    x_frac, y_frac = location
    bar_x0 = xmin + x_frac * (xmax - xmin) - length_m / 2
    bar_y0 = ymin + y_frac * (ymax - ymin)

    # Height of scale bar
    bar_height = map_width_m * 0.015

    # Draw segments
    for i in range(segments):
        x0 = bar_x0 + i * seg_len
        x1 = x0 + seg_len
        color = 'black' if i % 2 == 0 else 'white'
        ax.fill_between([x0, x1], bar_y0, bar_y0 + bar_height,
                        facecolor=color, edgecolor='black', zorder=3)
        # Label under each tick
        ax.text(x0, bar_y0 - (map_width_m*0.008), f"{int(i*total_km/segments)}",
                ha='center', va='top', fontsize=8)

    # Final label
    ax.text(bar_x0 + length_m, bar_y0 - (map_width_m*0.008), f"{total_km} km",
            ha='center', va='top', fontsize=8)

# --------------------------
# 4. CREATE PDF
# --------------------------
pdf_path = os.path.join(OUTPUT_FOLDER, PDF_FILENAME)
with PdfPages(pdf_path) as pdf:
    plt.rcParams['font.family'] = 'Arial'
    fig = plt.figure(figsize=(PAGE_WIDTH, PAGE_HEIGHT))

    # GridSpec: widen graphs (1.3 : 2 ratio)
    gs = gridspec.GridSpec(nrows=len(CATCHMENTS_OF_INTEREST), ncols=2,
                           width_ratios=[2, 2], hspace=0.6, wspace=0.3)

    # Left: stacked line graphs
    left_axes = [fig.add_subplot(gs[i, 0]) for i in range(len(CATCHMENTS_OF_INTEREST))]
    for ax, catch in zip(left_axes, CATCHMENTS_OF_INTEREST):
        gdf_c = gdf_samples_filtered[gdf_samples_filtered['OPCAT_NAME']==catch]
        if gdf_c.empty:
            continue
        mean_per_year = gdf_c.groupby('Year')['result'].mean().reset_index()
        ax.plot(mean_per_year['Year'], mean_per_year['result'], color='black', marker='o', linestyle='-', linewidth=1.2)
        ax.set_ylabel(f"{DETERMINAND} ({UNITS})", fontsize=8)
        ax.set_ylim(Y_MIN, Y_MAX)
        ax.set_title(catch, fontsize=9, fontstyle='italic')
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.tick_params(axis='y', labelsize=7)
        ax.tick_params(axis='x', labelsize=7)
        ax.set_xticks(sorted(mean_per_year['Year'].unique()))  # whole years
    left_axes[-1].set_xlabel("Year", fontsize=9)
    fig.text(0.05, 0.95, TIME_SERIES_TITLE, fontsize=12, fontweight='bold', ha='left', va='top')

    # Right: map
    ax_map = fig.add_subplot(gs[:, 1])
    catch_colors = ['#a6cee3','#7fb3d5','#6a3d9a']
    eqs_colors = {'Pass':'green', 'Fail':'red'}

    # Plot catchments
    catch_class = classify_adaptive(gdf_map_catchments['MEAN_result'])
    catch_bins = catch_class.bins
    cmap_catch = ListedColormap(catch_colors)
    norm_catch = BoundaryNorm([0]+list(catch_bins), ncolors=len(catch_colors))
    gdf_map_catchments.plot(column='MEAN_result', cmap=cmap_catch, norm=norm_catch,
                            edgecolor='black', ax=ax_map, missing_kwds={"color":"#b0b0b0"})

    # Plot rivers using 'eqs' field
    def get_eqs_color(val):
        if pd.isna(val):
            return '#b0b0b0'
        return eqs_colors.get(val, '#b0b0b0')

    gdf_map_rivers['color'] = gdf_map_rivers['eqs'].apply(get_eqs_color)
    gdf_map_rivers.plot(color=gdf_map_rivers['color'], linewidth=2, ax=ax_map)

    # Catchment labels
    label_offset = 0.01
    for name, group in gdf_map_catchments.groupby('OPCAT_NAME'):
        geom = group.unary_union
        if geom is None:
            continue
        x_cent, y_cent = geom.centroid.coords[0]
        minx, miny, maxx, maxy = geom.bounds
        width, height = maxx - minx, maxy - miny
        x_label, y_label = x_cent, y_cent + height*label_offset
        txt = ax_map.text(x_label, y_label, name, fontsize=7, ha='center', va='bottom',
                          fontweight='bold', color='black')
        txt.set_path_effects([path_effects.Stroke(linewidth=2, foreground='white'), path_effects.Normal()])

    # North arrow & scale bar
    add_north_arrow(ax_map)
    add_scale_bar(ax_map, total_km=20, segments=4)

    # Legends
    catch_handles = [mpatches.Patch(color=catch_colors[i],
                                    label=f"Catchments: {0 if i==0 else catch_bins[i-1]:.2f} – {catch_bins[i]:.2f} {UNITS}")
                     for i in range(len(catch_bins))]
    catch_handles.append(mpatches.Patch(color="#b0b0b0", label="Catchments: No Data"))
    river_handles = [mpatches.Patch(color='green', label='Rivers: Pass'),
                     mpatches.Patch(color='red', label='Rivers: Fail'),
                     mpatches.Patch(color='#b0b0b0', label='Rivers: No Data')]

    leg1 = ax_map.legend(handles=catch_handles, loc='upper right', fontsize=7, title="Catchments", title_fontsize=8)
    ax_map.add_artist(leg1)
    ax_map.legend(handles=river_handles, loc='lower right', fontsize=7, title="Rivers", title_fontsize=8)

    ax_map.set_title(SPATIAL_MAP_TITLE, fontsize=12, fontweight='bold')
    ax_map.axis('off')

    fig.suptitle(PDF_TITLE, fontsize=16, fontweight='bold')
    plt.tight_layout(rect=[0,0.05,1,0.93])
    pdf.savefig(fig)
    plt.close(fig)

print(f"✅ PDF created: {pdf_path}")

# ==========================
# Water Quality Monitoring Report (Graphs + Map)
# ==========================

import os
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import ListedColormap, BoundaryNorm
import matplotlib.patches as mpatches
import matplotlib.patheffects as path_effects
import mapclassify
import matplotlib.gridspec as gridspec
import numpy as np

# --------------------------
# 1. CONFIGURATION
# --------------------------
GDB_PATH = r"C:\Users\halza\OneDrive\Documents\ArcGIS\Projects\Yorkshire Project\Yorkshire Project.gdb"
OUTPUT_FOLDER = r"C:\Users\halza\OneDrive\Documents\ArcGIS\Projects\Yorkshire Project\Reports"
PDF_FILENAME = "Water_Quality_Monitoring.pdf"

SAMPLES_LAYER = "lead_samples"
CATCHMENTS_LAYER = "WFD_Catchments"
MAP_CATCHMENTS_LAYER = "Catchment_Samples"
MAP_RIVERS_LAYER = "River_Samples"

CATCHMENTS_OF_INTEREST = [
    "Colne and Holme", "Aire Lower", "Calder Lower",
    "Aire Middle", "Calder Middle", "Aire Upper", "Calder Upper"
]

PAGE_WIDTH, PAGE_HEIGHT = 16, 8.3  # wide figure for graphs
PDF_TITLE = "Water Quality Monitoring Report"
TIME_SERIES_TITLE = "Mean Lead Concentrations Over Time (2022–2024)"
SPATIAL_MAP_TITLE = "Spatial Distribution of Mean Lead (Pb)\nManagement Catchment: Aire & Calder (2022–2024)"
DETERMINAND = "Pb"
UNITS = "µg/L"

# --------------------------
# 2. LOAD DATA
# --------------------------
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

gdf_samples = gpd.read_file(GDB_PATH, layer=SAMPLES_LAYER)
gdf_catchments = gpd.read_file(GDB_PATH, layer=CATCHMENTS_LAYER)
gdf_map_catchments = gpd.read_file(GDB_PATH, layer=MAP_CATCHMENTS_LAYER)
gdf_map_rivers = gpd.read_file(GDB_PATH, layer=MAP_RIVERS_LAYER)

for df in [gdf_samples, gdf_catchments]:
    df.columns = df.columns.str.strip()

gdf_samples['sample_sampleDateTime'] = pd.to_datetime(gdf_samples['sample_sampleDateTime'])
gdf_samples['Year'] = gdf_samples['sample_sampleDateTime'].dt.year

if gdf_samples.crs != gdf_catchments.crs:
    gdf_samples = gdf_samples.to_crs(gdf_catchments.crs)

gdf_samples_joined = gpd.sjoin(
    gdf_samples,
    gdf_catchments[['OPCAT_NAME','geometry']],
    how='inner',
    predicate='within'
)

gdf_samples_filtered = gdf_samples_joined[
    gdf_samples_joined['OPCAT_NAME'].isin(CATCHMENTS_OF_INTEREST)
].copy()

for df in [gdf_map_catchments, gdf_map_rivers]:
    df['MEAN_result'] = pd.to_numeric(df['MEAN_result'], errors='coerce')

# --------------------------
# 3. HELPER FUNCTIONS
# --------------------------
def classify_adaptive(values, max_k=3):
    unique_vals = values.nunique()
    k = min(max_k, unique_vals if unique_vals > 1 else 1)
    return mapclassify.NaturalBreaks(values.dropna(), k=k)

def add_north_arrow(ax):
    ax.annotate('N', xy=(0.5, 0.97), xycoords='axes fraction',
                ha='center', va='bottom', fontsize=12, fontweight='bold')
    ax.arrow(0.5, 0.88, 0, 0.05, transform=ax.transAxes,
             head_width=0.02, head_length=0.03, fc='k', ec='k')

def add_scale_bar(ax, total_km=20, segments=4, location=(0.5, 0.05)):
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    map_width_m = xmax - xmin

    length_m = total_km * 1000
    if length_m > map_width_m:
        length_m = map_width_m * 0.25
        total_km = int(length_m / 1000)

    seg_len = length_m / segments

    x_frac, y_frac = location
    bar_x0 = xmin + x_frac * (xmax - xmin) - length_m / 2
    bar_y0 = ymin + y_frac * (ymax - ymin)
    bar_height = map_width_m * 0.015

    for i in range(segments):
        x0 = bar_x0 + i * seg_len
        x1 = x0 + seg_len
        color = 'black' if i % 2 == 0 else 'white'
        ax.fill_between([x0, x1], bar_y0, bar_y0 + bar_height,
                        facecolor=color, edgecolor='black', zorder=3)
        ax.text(x0, bar_y0 - (map_width_m*0.008), f"{int(i*total_km/segments)}",
                ha='center', va='top', fontsize=8)

    ax.text(bar_x0 + length_m, bar_y0 - (map_width_m*0.008), f"{total_km} km",
            ha='center', va='top', fontsize=8)

# --------------------------
# 4. CREATE PDF
# --------------------------
pdf_path = os.path.join(OUTPUT_FOLDER, PDF_FILENAME)
with PdfPages(pdf_path) as pdf:
    plt.rcParams['font.family'] = 'Arial'

    # --- PAGE 1: Line Graphs ---
    fig1 = plt.figure(figsize=(PAGE_WIDTH, PAGE_HEIGHT))

    # Global axis limits
    all_years = gdf_samples_filtered['Year']
    x_min, x_max = 2000, all_years.max()
    all_means = gdf_samples_filtered.groupby(['OPCAT_NAME','Year'])['result'].mean()
    y_min, y_max = 0, all_means.max() * 1.1

    gs = gridspec.GridSpec(nrows=len(CATCHMENTS_OF_INTEREST), ncols=1,
                           hspace=0.7)  # increase from 0.5 to 0.7 or 0.8

    left_axes = [fig1.add_subplot(gs[i, 0]) for i in range(len(CATCHMENTS_OF_INTEREST))]
    for ax, catch in zip(left_axes, CATCHMENTS_OF_INTEREST):
        gdf_c = gdf_samples_filtered[gdf_samples_filtered['OPCAT_NAME']==catch]
        if gdf_c.empty:
            continue
        mean_per_year = gdf_c.groupby('Year')['result'].mean().reset_index()

        ax.step(mean_per_year['Year'], mean_per_year['result'], where='mid', color='#1f77b4', linewidth=2)
        ax.plot(mean_per_year['Year'], mean_per_year['result'], 'o', color='#1f77b4', markersize=5)

        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)
        ax.set_xticks(range(x_min, x_max+1, 1))

        ax.set_ylabel(f"{DETERMINAND} ({UNITS})", fontsize=8)
        ax.set_title(catch, fontsize=8, fontstyle='italic')
        ax.tick_params(axis='y', labelsize=7)
        ax.tick_params(axis='x', labelsize=7)
    left_axes[-1].set_xlabel("Year", fontsize=9)
    fig1.text(0.05, 0.95, TIME_SERIES_TITLE, fontsize=12, fontweight='bold', ha='left', va='top')

    fig1.suptitle(PDF_TITLE, fontsize=16, fontweight='bold')
    plt.tight_layout(rect=[0,0.05,1,0.93])
    pdf.savefig(fig1)
    plt.close(fig1)

    # --- PAGE 2: Map ---
    fig2 = plt.figure(figsize=(PAGE_WIDTH, PAGE_HEIGHT))
    ax_map = fig2.add_subplot(1,1,1)

    # Catchments
    catch_colors = ['#a6cee3','#7fb3d5','#6a3d9a']
    catch_class = classify_adaptive(gdf_map_catchments['MEAN_result'])
    catch_bins = catch_class.bins
    cmap_catch = ListedColormap(catch_colors)
    norm_catch = BoundaryNorm([0]+list(catch_bins), ncolors=len(catch_colors))
    gdf_map_catchments.plot(column='MEAN_result', cmap=cmap_catch, norm=norm_catch,
                            edgecolor='black', ax=ax_map, missing_kwds={"color":"#b0b0b0"})

    # Rivers using 'eqs'
    eqs_colors = {'Pass':'green', 'Fail':'red'}
    gdf_map_rivers['color'] = gdf_map_rivers['eqs'].apply(lambda v: eqs_colors.get(v, '#b0b0b0'))
    gdf_map_rivers.plot(color=gdf_map_rivers['color'], linewidth=2, ax=ax_map)

    # Labels
    label_offset = 0.01
    for name, group in gdf_map_catchments.groupby('OPCAT_NAME'):
        geom = group.unary_union
        if geom is None:
            continue
        x_cent, y_cent = geom.centroid.coords[0]
        minx, miny, maxx, maxy = geom.bounds
        width, height = maxx - minx, maxy - miny
        x_label, y_label = x_cent, y_cent + height*label_offset
        txt = ax_map.text(x_label, y_label, name, fontsize=7, ha='center', va='bottom',
                          fontweight='bold', color='black')
        txt.set_path_effects([path_effects.Stroke(linewidth=2, foreground='white'), path_effects.Normal()])

    # North arrow & scale bar
    add_north_arrow(ax_map)
    add_scale_bar(ax_map, total_km=20, segments=4)

    # Legends
    catch_handles = [mpatches.Patch(color=catch_colors[i],
                                    label=f"Catchments: {0 if i==0 else catch_bins[i-1]:.2f} – {catch_bins[i]:.2f} {UNITS}")
                     for i in range(len(catch_bins))]
    catch_handles.append(mpatches.Patch(color="#b0b0b0", label="Catchments: No Data"))
    river_handles = [mpatches.Patch(color='green', label='Rivers: Pass'),
                     mpatches.Patch(color='red', label='Rivers: Fail'),
                     mpatches.Patch(color='#b0b0b0', label='Rivers: No Data')]

    leg1 = ax_map.legend(handles=catch_handles, loc='upper right', fontsize=7, title="Catchments", title_fontsize=8)
    ax_map.add_artist(leg1)
    ax_map.legend(handles=river_handles, loc='lower right', fontsize=7, title="Rivers", title_fontsize=8)

    ax_map.set_title(SPATIAL_MAP_TITLE, fontsize=12, fontweight='bold')
    ax_map.axis('off')

    pdf.savefig(fig2)
    plt.close(fig2)

print(f"✅ PDF created: {pdf_path}")

# ==========================
# Water Quality Monitoring Report (Graphs + Map)
# ==========================

import os
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import ListedColormap, BoundaryNorm
import matplotlib.patches as mpatches
import matplotlib.patheffects as path_effects
import mapclassify
import matplotlib.gridspec as gridspec

# --------------------------
# CONFIGURATION
# --------------------------
GDB_PATH = r"C:\Users\halza\OneDrive\Documents\ArcGIS\Projects\Yorkshire Project\Yorkshire Project.gdb"
OUTPUT_FOLDER = r"C:\Users\halza\OneDrive\Documents\ArcGIS\Projects\Yorkshire Project\Reports"
PDF_FILENAME = "Water_Quality_Monitoring.pdf"
SAMPLES_LAYER = "lead_samples"
BIO_LAYER = "bio_lead_samples"
CATCHMENTS_LAYER = "WFD_Catchments"
MAP_CATCHMENTS_LAYER = "Catchment_Samples"
MAP_RIVERS_LAYER = "River_Samples"
CATCHMENTS_OF_INTEREST = ["Colne and Holme", "Aire Lower", "Calder Lower", "Aire Middle", "Calder Middle", "Aire Upper", "Calder Upper"]
PAGE_WIDTH, PAGE_HEIGHT = 16, 8.3
PDF_TITLE = "Water Quality Monitoring Report"
TIME_SERIES_TITLE = "Mean Lead Concentrations Over Time (2022–2024)"
SPATIAL_MAP_TITLE = "Spatial Distribution of Mean Lead (Pb)\nManagement Catchment: Aire & Calder (2022–2024)"
DETERMINAND = "Pb"
UNITS = "µg/L"

# --------------------------
# LOAD DATA
# --------------------------
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def load_samples(layer_name):
    gdf = gpd.read_file(GDB_PATH, layer=layer_name)
    gdf.columns = gdf.columns.str.strip()
    gdf['sample_sampleDateTime'] = pd.to_datetime(gdf['sample_sampleDateTime'])
    gdf['Year'] = gdf['sample_sampleDateTime'].dt.year
    if gdf.crs != gdf_catchments.crs:
        gdf = gdf.to_crs(gdf_catchments.crs)
    return gpd.sjoin(gdf, gdf_catchments[['OPCAT_NAME','geometry']], how='inner', predicate='within')

gdf_catchments = gpd.read_file(GDB_PATH, layer=CATCHMENTS_LAYER)
gdf_samples = load_samples(SAMPLES_LAYER)
gdf_samples_filtered = gdf_samples[gdf_samples['OPCAT_NAME'].isin(CATCHMENTS_OF_INTEREST)]

gdf_bio_filtered = load_samples(BIO_LAYER)
gdf_bio_filtered = gdf_bio_filtered[gdf_bio_filtered['OPCAT_NAME'].isin(CATCHMENTS_OF_INTEREST)]

gdf_map_catchments = gpd.read_file(GDB_PATH, layer=MAP_CATCHMENTS_LAYER)
gdf_map_rivers = gpd.read_file(GDB_PATH, layer=MAP_RIVERS_LAYER)
for df in [gdf_map_catchments, gdf_map_rivers]: df['MEAN_result'] = pd.to_numeric(df['MEAN_result'], errors='coerce')

# --------------------------
# HELPER FUNCTIONS
# --------------------------

def classify_adaptive(values, max_k=3): return mapclassify.NaturalBreaks(values.dropna(), k=min(max_k, max(1, values.nunique())))

def add_north_arrow(ax):
    ax.annotate('N', xy=(0.5, 0.97), xycoords='axes fraction', ha='center', va='bottom', fontsize=12, fontweight='bold')
    ax.arrow(0.5, 0.90, 0, 0.05, transform=ax.transAxes, head_width=0.02, head_length=0.03, fc='k', ec='k')

def add_scale_bar(ax, total_km=20, segments=4, location=(0.5,0.05)):
    xmin,xmax = ax.get_xlim(); ymin,ymax=ax.get_ylim(); map_width=xmax-xmin
    length_m=total_km*1000; seg_len=length_m/segments; x_frac,y_frac=location
    bar_x0=xmin+x_frac*map_width-length_m/2; bar_y0=ymin+y_frac*(ymax-ymin); h=map_width*0.015
    for i in range(segments): x0=bar_x0+i*seg_len; x1=x0+seg_len; ax.fill_between([x0,x1], bar_y0, bar_y0+h, facecolor='black' if i%2==0 else 'white', edgecolor='black', zorder=3); ax.text(x0, bar_y0-map_width*0.008,f"{int(i*total_km/segments)}",ha='center',va='top',fontsize=8)
    ax.text(bar_x0+length_m, bar_y0-map_width*0.008,f"{total_km} km",ha='center',va='top',fontsize=8)

# --------------------------
# CREATE PDF
# --------------------------

pdf_path = os.path.join(OUTPUT_FOLDER, PDF_FILENAME)
with PdfPages(pdf_path) as pdf:
    plt.rcParams['font.family'] = 'Arial'

 # --- PAGE 1: Line Graphs (Two columns) ---
    fig1 = plt.figure(figsize=(PAGE_WIDTH, PAGE_HEIGHT))
    x_min, x_max = 2000, max(gdf_samples_filtered['Year'].max(), gdf_bio_filtered['Year'].max())
    y_max_lead = gdf_samples_filtered.groupby(['OPCAT_NAME','Year'])['result'].mean().max()*1.1
    y_max_bio = gdf_bio_filtered.groupby(['OPCAT_NAME','Year'])['result'].mean().max()*1.1
    
    
    gs = gridspec.GridSpec(nrows=len(CATCHMENTS_OF_INTEREST), ncols=2, width_ratios=[1,1], hspace=0.7, wspace=0.3)
    
    
    # Left column: Lead Samples
    for i, catch in enumerate(CATCHMENTS_OF_INTEREST):
            ax = fig1.add_subplot(gs[i,0])
        df1 = gdf_samples_filtered[gdf_samples_filtered['OPCAT_NAME']==catch].groupby('Year')['result'].mean().reset_index()
        if not df1.empty:
            ax.step(df1['Year'], df1['result'], where='mid', color='black', linewidth=2)
            ax.plot(df1['Year'], df1['result'],'o',color='black',markersize=5)
        ax.set_xlim(x_min, x_max); ax.set_ylim(0, y_max_lead)
        ax.set_ylabel(f"{DETERMINAND} ({UNITS})", fontsize=8)
        ax.set_title(catch, fontsize=9, fontstyle='italic', pad=10)
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.tick_params(axis='y', labelsize=7); ax.tick_params(axis='x', labelsize=7)
    
    
    # Right column: Bio Lead Samples
    for i, catch in enumerate(CATCHMENTS_OF_INTEREST):
        ax = fig1.add_subplot(gs[i,1])
        df2 = gdf_bio_filtered[gdf_bio_filtered['OPCAT_NAME']==catch].groupby('Year')['result'].mean().reset_index()
        if not df2.empty:
            ax.step(df2['Year'], df2['result'], where='mid', color='green', linewidth=2)
            ax.plot(df2['Year'], df2['result'],'o',color='green',markersize=5)
        ax.set_xlim(x_min, x_max); ax.set_ylim(0, y_max_bio)
        ax.set_ylabel(f"{DETERMINAND} ({UNITS})", fontsize=8)
        ax.set_title(catch, fontsize=9, fontstyle='italic', pad=10)
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.tick_params(axis='y', labelsize=7); ax.tick_params(axis='x', labelsize=7)
    
    
    fig1.text(0.05,0.95,TIME_SERIES_TITLE,fontsize=12,fontweight='bold',ha='left',va='top')
    fig1.suptitle(PDF_TITLE, fontsize=16,fontweight='bold')
    plt.tight_layout(rect=[0,0.05,1,0.93])
    pdf.savefig(fig1); plt.close(fig1)
    # --- PAGE 2: Map ---
    fig2 = plt.figure(figsize=(PAGE_WIDTH, PAGE_HEIGHT))
    ax_map = fig2.add_subplot(1,1,1)

    catch_colors = ['#a6cee3','#7fb3d5','#6a3d9a']
    catch_class = classify_adaptive(gdf_map_catchments['MEAN_result']); catch_bins=catch_class.bins
    cmap_catch = ListedColormap(catch_colors); norm_catch=BoundaryNorm([0]+list(catch_bins),ncolors=len(catch_colors))
                                                gdf_map_catchments.plot(column='MEAN_result',cmap=cmap_catch,norm=norm_catch,edgecolor='black',ax=ax_map,missing_kwds={"color":"#b0b0b0"})

    eqs_colors={'Pass':'green','Fail':'red'}
    gdf_map_rivers['color'] = gdf_map_rivers['eqs'].apply(lambda v:eqs_colors.get(v,'#b0b0b0'))
    gdf_map_rivers.plot(color=gdf_map_rivers['color'],linewidth=2,ax=ax_map)

    for name, group in gdf_map_catchments.groupby('OPCAT_NAME'):
        geom = group.unary_union
        if geom is None: continue
        x_cent, y_cent = geom.centroid.coords[0]
        minx, miny, maxx, maxy = geom.bounds
        x_label, y_label = x_cent, y_cent + (maxy-miny)*0.01
        txt = ax_map.text(x_label, y_label, name, fontsize=7, ha='center', va='bottom', fontweight='bold', color='black')
        txt.set_path_effects([path_effects.Stroke(linewidth=2, foreground='white'), path_effects.Normal()])

    add_north_arrow(ax_map)
    add_scale_bar(ax_map, total_km=20, segments=4)

    catch_handles = [mpatches.Patch(color=catch_colors[i], label=f"Catchments: {0 if i==0 else catch_bins[i-1]:.2f} – {catch_bins[i]:.2f} {UNITS}") for i in range(len(catch_bins))]
    catch_handles.append(mpatches.Patch(color="#b0b0b0", label="Catchments: No Data"))
    river_handles = [mpatches.Patch(color='green', label='Rivers: Pass'), mpatches.Patch(color='red', label='Rivers: Fail'), mpatches.Patch(color='#b0b0b0', label='Rivers: No Data')]

    leg1 = ax_map.legend(handles=catch_handles, loc='upper right', fontsize=7, title="Catchments", title_fontsize=8)
    ax_map.add_artist(leg1)
    ax_map.legend(handles=river_handles, loc='lower right', fontsize=7, title="Rivers", title_fontsize=8)
    ax_map.set_title(SPATIAL_MAP_TITLE, fontsize=12, fontweight='bold')
    ax_map.axis('off')

    pdf.savefig(fig2)
    plt.close(fig2)

print(f"✅ PDF created: {pdf_path}")

# ==========================
# Water Quality Monitoring Report (Graphs + Map)
# ==========================

import os
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import ListedColormap, BoundaryNorm
import matplotlib.patches as mpatches
import matplotlib.patheffects as path_effects
import mapclassify
import matplotlib.gridspec as gridspec

# --------------------------
# CONFIGURATION
# --------------------------
GDB_PATH = r"C:\Users\halza\OneDrive\Documents\ArcGIS\Projects\Yorkshire Project\Yorkshire Project.gdb"
OUTPUT_FOLDER = r"C:\Users\halza\OneDrive\Documents\ArcGIS\Projects\Yorkshire Project\Reports"
PDF_FILENAME = "Water_Quality_Monitoring.pdf"
SAMPLES_LAYER = "lead_samples"
BIO_LAYER = "bio_lead_samples"
CATCHMENTS_LAYER = "WFD_Catchments"
MAP_CATCHMENTS_LAYER = "Catchment_Samples"
MAP_RIVERS_LAYER = "River_Samples"
CATCHMENTS_OF_INTEREST = ["Colne and Holme", "Aire Lower", "Calder Lower", "Aire Middle", "Calder Middle", "Aire Upper", "Calder Upper"]
PAGE_WIDTH, PAGE_HEIGHT = 16, 8.3
PDF_TITLE = "Water Quality Monitoring Report"
TIME_SERIES_TITLE = "Mean Lead Concentrations (µg/L) Over Time (2000–2025)"
SPATIAL_MAP_TITLE = "Spatial Distribution of Mean Lead (µg/L)\nManagement Catchment: Aire & Calder (2022–2024)"
DETERMINAND = "Pb"
UNITS = "µg/L"

# --------------------------
# LOAD DATA
# --------------------------
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def load_samples(layer_name):
    gdf = gpd.read_file(GDB_PATH, layer=layer_name)
    gdf.columns = gdf.columns.str.strip()
    gdf['sample_sampleDateTime'] = pd.to_datetime(gdf['sample_sampleDateTime'])
    gdf['Year'] = gdf['sample_sampleDateTime'].dt.year
    if gdf.crs != gdf_catchments.crs:
        gdf = gdf.to_crs(gdf_catchments.crs)
    return gpd.sjoin(gdf, gdf_catchments[['OPCAT_NAME','geometry']], how='inner', predicate='within')

gdf_catchments = gpd.read_file(GDB_PATH, layer=CATCHMENTS_LAYER)
gdf_samples = load_samples(SAMPLES_LAYER)
gdf_samples_filtered = gdf_samples[gdf_samples['OPCAT_NAME'].isin(CATCHMENTS_OF_INTEREST)]

gdf_bio_filtered = load_samples(BIO_LAYER)
gdf_bio_filtered = gdf_bio_filtered[gdf_bio_filtered['OPCAT_NAME'].isin(CATCHMENTS_OF_INTEREST)]

gdf_map_catchments = gpd.read_file(GDB_PATH, layer=MAP_CATCHMENTS_LAYER)
gdf_map_rivers = gpd.read_file(GDB_PATH, layer=MAP_RIVERS_LAYER)
for df in [gdf_map_catchments, gdf_map_rivers]: df['MEAN_result'] = pd.to_numeric(df['MEAN_result'], errors='coerce')

# --------------------------
# HELPER FUNCTIONS
# --------------------------

def classify_adaptive(values, max_k=3): return mapclassify.NaturalBreaks(values.dropna(), k=min(max_k, max(1, values.nunique())))

def add_north_arrow(ax):
    ax.annotate('N', xy=(0.5, 0.97), xycoords='axes fraction', ha='center', va='bottom', fontsize=12, fontweight='bold')
    ax.arrow(0.5, 0.88, 0, 0.05, transform=ax.transAxes, head_width=0.02, head_length=0.03, fc='k', ec='k')

def add_scale_bar(ax, total_km=20, segments=4, location=(0.5,0.05)):
    xmin,xmax = ax.get_xlim(); ymin,ymax=ax.get_ylim(); map_width=xmax-xmin
    length_m=total_km*1000; seg_len=length_m/segments; x_frac,y_frac=location
    bar_x0=xmin+x_frac*map_width-length_m/2; bar_y0=ymin+y_frac*(ymax-ymin); h=map_width*0.015
    for i in range(segments): x0=bar_x0+i*seg_len; x1=x0+seg_len; ax.fill_between([x0,x1], bar_y0, bar_y0+h, facecolor='black' if i%2==0 else 'white', edgecolor='black', zorder=3); ax.text(x0, bar_y0-map_width*0.008,f"{int(i*total_km/segments)}",ha='center',va='top',fontsize=8)
    ax.text(bar_x0+length_m, bar_y0-map_width*0.008,f"{total_km} km",ha='center',va='top',fontsize=8)

# --------------------------
# CREATE PDF
# --------------------------

pdf_path = os.path.join(OUTPUT_FOLDER, PDF_FILENAME)
with PdfPages(pdf_path) as pdf:
    plt.rcParams['font.family'] = 'Arial'

    # --- PAGE 1: Line Graphs (Two columns) ---
    fig1 = plt.figure(figsize=(PAGE_WIDTH, PAGE_HEIGHT))
    x_min, x_max = 2000, max(gdf_samples_filtered['Year'].max(), gdf_bio_filtered['Year'].max())
    y_max_lead = gdf_samples_filtered.groupby(['OPCAT_NAME','Year'])['result'].mean().max()*1.1
    y_max_bio = gdf_bio_filtered.groupby(['OPCAT_NAME','Year'])['result'].mean().max()*1.1

    gs = gridspec.GridSpec(nrows=len(CATCHMENTS_OF_INTEREST), ncols=2, width_ratios=[1,1], hspace=0.7, wspace=0.3)

    # Left column: Lead Samples
    for i, catch in enumerate(CATCHMENTS_OF_INTEREST):
        ax = fig1.add_subplot(gs[i,0])
        df1 = gdf_samples_filtered[gdf_samples_filtered['OPCAT_NAME']==catch].groupby('Year')['result'].mean().reset_index()
        if not df1.empty:
            ax.step(df1['Year'], df1['result'], where='mid', color='black', linewidth=2)
            ax.plot(df1['Year'], df1['result'],'o',color='black',markersize=5)
        ax.set_xlim(x_min, x_max); ax.set_ylim(0, y_max_lead)
        ax.set_ylabel(f"{DETERMINAND} ({UNITS})", fontsize=8)
        ax.set_title(catch, fontsize=9, fontstyle='italic', pad=10)
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.tick_params(axis='y', labelsize=7); ax.tick_params(axis='x', labelsize=7)

    # Right column: Bio Lead Samples
    for i, catch in enumerate(CATCHMENTS_OF_INTEREST):
        ax = fig1.add_subplot(gs[i,1])
        df2 = gdf_bio_filtered[gdf_bio_filtered['OPCAT_NAME']==catch].groupby('Year')['result'].mean().reset_index()
        if not df2.empty:
            ax.step(df2['Year'], df2['result'], where='mid', color='green', linewidth=2)
            ax.plot(df2['Year'], df2['result'],'o',color='green',markersize=5)
        ax.set_xlim(x_min, x_max); ax.set_ylim(0, y_max_bio)
        ax.set_ylabel(f"{DETERMINAND} ({UNITS})", fontsize=8)
        ax.set_title(catch, fontsize=9, fontstyle='italic', pad=10)
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.tick_params(axis='y', labelsize=7); ax.tick_params(axis='x', labelsize=7)

    fig1.text(0.05,0.95,TIME_SERIES_TITLE,fontsize=12,fontweight='bold',ha='left',va='top')
    fig1.suptitle(PDF_TITLE, fontsize=16,fontweight='bold')
    plt.tight_layout(rect=[0,0.05,1,0.93])
    pdf.savefig(fig1); plt.close(fig1)

    # --- PAGE 2: Map ---
    fig2 = plt.figure(figsize=(PAGE_WIDTH, PAGE_HEIGHT))
    ax_map = fig2.add_subplot(1,1,1)
    
    # Catchments symbology
    catch_colors = ['#a6cee3','#7fb3d5','#6a3d9a']
    catch_class = classify_adaptive(gdf_map_catchments['MEAN_result'])
    catch_bins = catch_class.bins
    cmap_catch = ListedColormap(catch_colors)
    norm_catch = BoundaryNorm([0] + list(catch_bins), ncolors=len(catch_colors))
    
    gdf_map_catchments.plot(
        column='MEAN_result',
        cmap=cmap_catch,
        norm=norm_catch,
        edgecolor='black',
        ax=ax_map,
        missing_kwds={"color": "#b0b0b0"}
    )

    # River symbology
    eqs_colors = {'Pass': 'green', 'Fail': 'red'}
    gdf_map_rivers['color'] = gdf_map_rivers['eqs'].apply(lambda v: eqs_colors.get(v, '#b0b0b0'))
    gdf_map_rivers.plot(
        color=gdf_map_rivers['color'],
        linewidth=2,
        ax=ax_map
    )

    # Add catchment labels
    for name, group in gdf_map_catchments.groupby('OPCAT_NAME'):
        geom = group.unary_union
        if geom is None:
            continue
        x_cent, y_cent = geom.centroid.coords[0]
        minx, miny, maxx, maxy = geom.bounds
        x_label, y_label = x_cent, y_cent + (maxy - miny) * 0.01
        txt = ax_map.text(
            x_label, y_label, name,
            fontsize=7, ha='center', va='bottom',
            fontweight='bold', color='black'
        )
        txt.set_path_effects([
            path_effects.Stroke(linewidth=2, foreground='white'),
            path_effects.Normal()
        ])

    # North arrow + scale bar
    add_north_arrow(ax_map)
    add_scale_bar(ax_map, total_km=20, segments=4)

    # Legends
    catch_handles = [
        mpatches.Patch(
            color=catch_colors[i],
            label=f"Catchments: {0 if i==0 else catch_bins[i-1]:.2f} – {catch_bins[i]:.2f} {UNITS}"
        )
        for i in range(len(catch_bins))
    ]
    catch_handles.append(mpatches.Patch(color="#b0b0b0", label="Catchments: No Data"))
    river_handles = [
        mpatches.Patch(color='green', label='Rivers: Pass'),
        mpatches.Patch(color='red', label='Rivers: Fail'),
        mpatches.Patch(color='#b0b0b0', label='Rivers: No Data')
    ]

    leg1 = ax_map.legend(handles=catch_handles, loc='upper right', fontsize=7, title="Catchments", title_fontsize=8)
    ax_map.add_artist(leg1)
    ax_map.legend(handles=river_handles, loc='lower right', fontsize=7, title="Rivers", title_fontsize=8)

    ax_map.set_title(SPATIAL_MAP_TITLE, fontsize=12, fontweight='bold')
    ax_map.axis('off')

    pdf.savefig(fig2)
    plt.close(fig2)


print(f"✅ PDF created: {pdf_path}")


