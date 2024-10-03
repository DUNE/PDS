import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Numeri delle celle (esattamente come nella tua immagine)
numeri = [
    ['104-7', '104-5', '104-2', '104-0', '109-27', '109-25', '109-22', '109-20', '111-1', '111-3', '111-4', '111-6', '112-0', '112-2', '112-5', '112-7'],
    ['104-1', '104-3', '104-4', '104-6', '109-21', '109-23', '109-24', '109-26', '111-36', '111-34', '111-33', '111-31', '112-6', '112-4', '112-3', '112-1'],
    ['104-17', '104-15', '104-12', '104-10', '109-37', '109-35', '109-32', '109-30', '111-0', '111-2', '111-5', '111-7', '112-10', '112-12', '112-15', '112-17'],
    ['104-11', '104-13', '104-14', '104-16', '109-31', '109-33', '109-34', '109-36', '111-37', '111-35', '111-32', '111-30', '112-16', '112-14*', '112-13', '112-11'],
    ['105-7', '105-5', '105-2', '105-0', '109-7', '109-5', '109-2', '109-0', '111-41', '111-43', '111-44', '111-46', '113-0', '113-2', '113-5', '113-7'],
    ['105-1', '105-3', '105-4', '105-6', '109-1', '109-3', '109-4', '109-6', '111-16', '111-14', '111-13', '111-11', '112-27', '112-25', '112-22+0.6V', '112-20'],
    ['105-26', '105-24', '105-23', '105-21', '109-17', '109-15', '109-12', '109-10', '111-10', '111-12', '111-15', '111-17', '112-21', '112-23', '112-24', '112-26'],
    ['105-10', '105-12', '105-15', '105-17', '109-11', '109-13', '109-14', '109-16', '111-26', '111-24', '111-23', '111-21', '112-37', '112-35', '112-32', '112-30'],
    ['107-17', '107-15', '107-12', '107-10+2.0V', '109-47', '109-45', '109-42', '109-40', '111-40', '111-42', '111-45', '111-47', '112-31', '112-33+0.86V', '112-34', '112-36'],
    ['107-0', '107-2', '107-5', '107-7', '109-41', '109-43', '109-44', '109-46', '111-27', '111-25', '111-22', '111-20', '112-47', '112-45', '112-42','112-40']
]

# Celle da colorare con colori specifici
celle_colori = {
    '107-0': 'yellow', '107-2': 'yellow', '107-5': 'yellow', '107-7': 'yellow', '109-15': 'yellow', '109-12': 'yellow',
    '107-10': 'purple', '112-11': 'purple', '112-22': 'purple', '112-33': 'purple',
    '109-10': 'red', '109-11': 'red', '109-13': 'red', '109-14': 'red', '109-16': 'red', '109-17': 'red'
}

# Impostazioni della figura
fig, ax = plt.subplots(figsize=(12, 8))

# Dimensioni delle celle
cell_width = 1
cell_height = 1

# Funzione per disegnare un rettangolo
def draw_rectangle(ax, x, y, width, height, color, text):
    rect = patches.Rectangle((x, y), width, height, linewidth=1, edgecolor='black', facecolor=color)
    ax.add_patch(rect)
    text_split = text.split('+')
    plt.text(x + width / 2, y + height / 2 + 0.1, text_split[0], ha='center', va='center', fontsize=8)
    if len(text_split) > 1:
        plt.text(x + width / 2, y + height / 2 - 0.3, f'+{text_split[1]}', ha='center', va='center', fontsize=6)

# Disegna le celle
for i in range(4):  # 4 rettangoli
    for j in range(10):  # 10 righe
        for k in range(4):  # 4 colonne
            x = i * 4 + k
            y = 9 - j
            numero = numeri[j][i * 4 + k]
            colore = celle_colori.get(numero.split('+')[0], 'green')
            draw_rectangle(ax, x, y, cell_width, cell_height, colore, numero)

# Disegna le linee di separazione
for i in range(1, 4):
    plt.plot([i * 4, i * 4], [0, 10], color='black', linewidth=2)

# Aggiungi bordi esterni più spessi
plt.plot([0, 16], [0, 0], color='black', linewidth=4)
plt.plot([0, 16], [10, 10], color='black', linewidth=4)
plt.plot([0, 0], [0, 10], color='black', linewidth=4)
plt.plot([16, 16], [0, 10], color='black', linewidth=4)

# Aggiungi etichette sotto ciascun rettangolo
for i, label in enumerate(['APA 1', 'APA 2', 'APA 3', 'APA 4']):
    plt.text(i * 4 + 2, -1, label, ha='center', va='center', fontsize=12)

# Aggiungi la didascalia sotto l'immagine
plt.text(8, -1.7, 'LEGEND:', ha='center', va='center', fontsize=8, color='black', fontweight='bold')
plt.text(8, -2, r'Green $\rightarrow$ Good IV curve and $V_{bd}$', ha='center', va='center', fontsize=8, color='green')
plt.text(8, -2.3, r'Yellow $\rightarrow$ Noisy IV curve', ha='center', va='center', fontsize=8, color='gold')
plt.text(8, -2.6, r'Purple $\rightarrow$ Steep IV curve and low $V_{bd}$', ha='center', va='center', fontsize=8, color='purple')
plt.text(8, -2.9, r'Red $\rightarrow$ Disconnected channel', ha='center', va='center', fontsize=8, color='red')
plt.text(8, -3.2, r'* $\rightarrow$ Hard to acquire IV curve (few data)', ha='center', va='center', fontsize=6, color='black')
plt.text(8, -3.5, r'P.S. : endpoint 107 was replaced by 110', ha='center', va='center', fontsize=6, color='black')

# Impostazioni degli assi
ax.set_xlim(0, 16)
ax.set_ylim(-4, 10)
ax.set_aspect('equal')
ax.axis('off')
plt.suptitle('IV and Vbd map', fontsize=18, color='black', fontweight='bold')

# Salva l'immagine
plt.savefig('/afs/cern.ch/user/a/anbalbon/IV_curve/PDS/data/iv_analysis/Vbd_heatmap.png', dpi=300, bbox_inches='tight')

# Mostra l'immagine (opzionale)
plt.show()
