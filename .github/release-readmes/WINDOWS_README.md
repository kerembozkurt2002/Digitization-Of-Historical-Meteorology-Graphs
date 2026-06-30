# Thermogram Digitizer — Windows Kurulum

ZIP arşivinde iki kurulum dosyası bulunur:

- `Thermogram Digitizer_*_x64-setup.exe` — NSIS installer (önerilen)
- `Thermogram Digitizer_*_x64_en-US.msi` — MSI installer (alternatif)

İkisi de aynı uygulamayı kurar. Yalnızca birini çalıştırın, diğerini ihtiyacınız olmazsa silebilirsiniz.

---

## Kurulum Adımları

1. ZIP arşivini çıkarın.
2. `*_x64-setup.exe` dosyasına çift tıklayın.
3. **"Windows protected your PC"** uyarısı çıkarsa:
   - Pencerede üstte küçük gri **More info** linkine tıklayın.
   - Alttaki **Run anyway** butonuna basın.
4. Installer adımlarını takip edin: **Next** → **Install** → **Finish**.
5. Başlat menüsünde **Thermogram Digitizer** yazıp uygulamayı açın.

---

## Neden SmartScreen Uyarısı Çıkıyor?

Uygulama Microsoft tarafından tanınan ücretli bir kod imzalama sertifikası (EV Code Signing Certificate) ile imzalanmadığı için, Windows internet üzerinden indirilen imzasız uygulamaları otomatik olarak güvenlik filtresine takar.

Bu uygulamanın kendisi güvenlidir — kaynak kodu açıktır ve doğrudan GitHub'da derlenmiştir. Sertifikanın yokluğu güvenlik sorunu değil, sadece tanıtım eksikliğidir.

---

## Kaldırma

**Ayarlar** → **Apps** → **Installed apps** → **Thermogram Digitizer** → **Uninstall**.

---

## Sorun Giderme

- **Uygulama açılmıyor / hemen kapanıyor:** Antivirüs yazılımınız uygulamayı karantinaya almış olabilir. Antivirüs istisnalarına ekleyin veya uygulamayı kuran kullanıcının yönetici yetkisiyle başlatın.
- **"Thermogram Digitizer is not responding":** İlk açılışta Python backend'in dylib'leri Windows tarafından doğrulanır (~5-10 saniye). Sonraki açılışlar ve işlemler çok hızlıdır.
