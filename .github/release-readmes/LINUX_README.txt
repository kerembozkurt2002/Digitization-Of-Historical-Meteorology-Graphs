# Thermogram Digitizer — Linux Kurulum

ZIP arşivinde tek bir kurulum dosyası bulunur:

- `Thermogram Digitizer_*_amd64.deb` — Debian / Ubuntu paketi

Ubuntu 22.04 ve üzeri ile Debian 11 ve üzerinde test edilmiştir.

---

## Kurulum

1. Paketi kurun:

   ```bash
   sudo dpkg -i Thermogram\ Digitizer_*_amd64.deb
   ```

2. Eksik bağımlılık olursa onarın:

   ```bash
   sudo apt-get install -f
   ```

3. Uygulamayı başlatın — Uygulamalar menüsünde **Thermogram Digitizer** olarak görünür. Terminalden:

   ```bash
   thermogram-digitizer
   ```

---

## Kaldırma

```bash
sudo apt remove thermogram-digitizer
```

---

## Sorun Giderme

- **`libwebkit2gtk-4.1-0` bulunamadı:** Eski bir dağıtım kullanıyorsunuz. Ubuntu 22.04+ veya Debian 12+ gerekir.
  ```bash
  sudo apt install libwebkit2gtk-4.1-0
  ```
- **Uygulama açılmıyor / siyah pencere:** WebKit sürücüsü sorun çıkarıyor olabilir. Terminalden başlatıp hata mesajını okuyun:
  ```bash
  thermogram-digitizer
  ```
- **Ubuntu 24.04 / Fedora gibi farklı dağıtım:** `.deb` Ubuntu/Debian'a özel. Diğer dağıtımlarda alien gibi araçlarla dönüştürmek yerine, kaynak koddan derlemeyi tercih edin (repo'daki README'ye bakın).
