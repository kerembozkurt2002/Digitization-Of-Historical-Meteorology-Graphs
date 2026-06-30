# Thermogram Digitizer — Linux Kurulum

ZIP arşivinde iki kurulum dosyası bulunur:

- `Thermogram Digitizer_*_amd64.AppImage` — taşınabilir, dağıtım bağımsız
- `Thermogram Digitizer_*_amd64.deb` — Debian / Ubuntu paket yöneticisi için

---

## Seçenek 1 — AppImage (önerilen)

AppImage tek dosyadır, kurulum gerektirmez, herhangi bir Linux dağıtımında çalışır.

1. Dosyayı çalıştırılabilir olarak işaretleyin:

   ```bash
   chmod +x "Thermogram Digitizer_"*.AppImage
   ```

2. Çift tıklayarak veya terminalden çalıştırın:

   ```bash
   ./Thermogram\ Digitizer_*.AppImage
   ```

3. Eğer `dlopen(): error loading libfuse.so.2` veya benzeri hata alırsanız, FUSE 2 kütüphanesini yükleyin:

   **Ubuntu / Debian:**
   ```bash
   sudo apt install libfuse2
   ```

   **Fedora:**
   ```bash
   sudo dnf install fuse
   ```

   **Arch / Manjaro:**
   ```bash
   sudo pacman -S fuse2
   ```

---

## Seçenek 2 — `.deb` (Ubuntu / Debian)

1. Paketi kurun:

   ```bash
   sudo dpkg -i Thermogram-Digitizer_*_amd64.deb
   ```

2. Eksik bağımlılık olursa onarın:

   ```bash
   sudo apt-get install -f
   ```

3. Uygulamayı başlatın — Uygulamalar menüsünde **Thermogram Digitizer** olarak görünür, ya da terminalden:

   ```bash
   thermogram-digitizer
   ```

---

## Kaldırma

- **AppImage:** Dosyayı silmeniz yeterli.
- **`.deb`:**
  ```bash
  sudo apt remove thermogram-digitizer
  ```

---

## Sorun Giderme

- **"webkit2gtk not found":** Sisteminizde WebKit2GTK 4.1 kurulu değil.
  ```bash
  sudo apt install libwebkit2gtk-4.1-0
  ```
- **`.deb` Ubuntu 24.04'te kurulmuyor:** AppImage tercih edin, çünkü yeni Ubuntu sürümleri WebKit ABI uyumsuzluğu yaşayabilir.
- **Uygulama açılmıyor:** Terminal üzerinden çalıştırıp hata mesajlarını görün:
  ```bash
  ./Thermogram\ Digitizer_*.AppImage
  ```
