import os

import matplotlib.pyplot as plt

years = list(range(2000, 2024))
emissions = [
    23.7, 24.1, 24.6, 25.2, 25.9, 26.6, 27.3, 28.0, 28.5, 27.8,
    29.0, 29.8, 30.4, 31.0, 31.7, 32.2, 32.8, 33.3, 33.9, 34.2,
    31.7, 33.4, 34.2, 34.9,
]

output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'exports')
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, 'world_co2_emissions_scatter_2000-2023.png')

plt.style.use('seaborn-v0_8-whitegrid')
fig, ax = plt.subplots(figsize=(12, 7), dpi=150)
ax.scatter(years, emissions, s=60, color='#0f7b8d', edgecolors='white', linewidth=0.8, alpha=0.9)
ax.plot(years, emissions, color='#0f7b8d', linewidth=1.5, alpha=0.5)

ax.set_title('Global CO2 emissions from fuel combustion', fontsize=18, weight='bold', pad=18)
ax.set_xlabel('Year', fontsize=12)
ax.set_ylabel('Emissions (billion tonnes)', fontsize=12)
ax.set_xlim(1999, 2024)
ax.set_ylim(20, 38)
ax.set_xticks(range(2000, 2024, 2))
ax.grid(True, axis='both', linestyle='-', linewidth=0.8, alpha=0.25)
ax.tick_params(labelsize=10)

for spine in ['top', 'right']:
    ax.spines[spine].set_visible(False)

# match the reference chart aesthetic with a light annotation near the latest point
latest_year = years[-1]
latest_value = emissions[-1]
ax.annotate(
    f'{latest_value:.1f} billion tonnes',
    xy=(latest_year, latest_value),
    xytext=(latest_year - 2, latest_value + 1.5),
    fontsize=12,
    color='#cf5b2c',
    weight='bold',
    arrowprops=dict(arrowstyle='-', color='#cf5b2c', lw=1.2)
)

fig.tight_layout()
fig.savefig(output_path, bbox_inches='tight')
print(f'Saved scatter plot to {output_path}')
