import pandas as pd

# İlk 10 satırı başlıksız oku
df = pd.read_excel("/home/kaan/Downloads/arac-fiyat-tahmin/filo_importer/data/filo_takip_20260727_104533.xls", engine="xlrd", header=1)
df.columns = df.columns.astype(str).str.strip()
df = df[~df["Plaka Durum"].isin(["Satıldı-İade"])]

rapor = (
    df.groupby(["Marka", "Araç Tip", "Versiyon"])
      .size()
      .reset_index(name="Araç Sayısı")
      .sort_values(["Marka", "Araç Tip", "Versiyon"])
)

rapor.to_excel("Arac_Raporu.xlsx", index=False)

print(rapor)