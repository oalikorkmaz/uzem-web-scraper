# scraper_refactored.py

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

import time

class UzemScraper:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.login_url = "https://uzem.msu.edu.tr/login/index.php"
        self.dashboard_url = "https://uzem.msu.edu.tr/"
        self.driver = None

    def connect_driver(self):
        """
        Remote Selenium WebDriver'a (Docker konteyneri) optimize edilmiş ayarlarla bağlanır.
        """
        print("Remote Chrome WebDriver'a (Docker) optimize edilmiş ayarlarla bağlanılıyor...")
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--headless=new')  # Headless
            options.page_load_strategy = 'none'     # Tam yüklemeyi bekleme

            # Arka plan ağ istekleri vs.
            options.add_argument('--disable-background-networking')
            options.add_argument('--disable-sync')
            options.add_argument('--disable-component-update')
            options.add_argument('--disable-default-apps')
            options.add_argument('--no-pings')
            options.add_argument('--disable-domain-reliability')
            options.add_argument('--disable-features=OptimizationHints,MediaRouter')

            # Görselleri kapat (ek)
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.managed_default_content_settings.plugins": 2,
            }
            options.add_experimental_option("prefs", prefs)

            self.driver = webdriver.Remote(
                command_executor='http://selenium_chrome:4444/wd/hub',
                options=options
            )

            # CDP: Ağ filtreleri
            self.driver.execute_cdp_cmd('Network.enable', {})
            self.driver.execute_cdp_cmd('Network.setBlockedURLs', {
                'urls': [
                    '*.png','*.jpg','*.jpeg','*.gif','*.webp','*.svg','*.ico',
                    '*.mp4','*.webm','*.mp3','*.wav','*.ogg',
                    '*.woff','*.woff2','*.ttf','*.otf',
                    '*.css',
                    '*googletagmanager*','*google-analytics*','*doubleclick*',
                    '*facebook*','*hotjar*','*sentry*','*clarity*','*newrelic*','*datadoghq*',
                    '*gravatar*','*youtube*','*vimeo*'
                ]
            })


            print("Remote WebDriver'a başarıyla bağlanıldı.")
            self.driver.set_page_load_timeout(120)
            return True
            
        except Exception as e:
            print(f"Remote WebDriver'a bağlanırken hata oluştu: {e}")
            return False

    def login(self):
        """Uzem.msu.edu.tr adresine giriş yapar."""
        if not self.driver:
            print("Hata: WebDriver başlatılmamış.")
            return False

        print(f"Giriş sayfasına gidiliyor: {self.login_url}")
        self.driver.get(self.login_url)

        try:
            # Elementlerin yüklenmesi için 30 saniyeye kadar bekle
            wait = WebDriverWait(self.driver, 60)

            # Sizin kodunuzdaki giriş mantığı
            username_field = wait.until(EC.presence_of_element_located((By.NAME, "username")))
            password_field = self.driver.find_element(By.NAME, "password")
            login_button = self.driver.find_element(By.ID, "loginbtn")

            username_field.send_keys(self.username)
            password_field.send_keys(self.password)
            login_button.click()

            # Giriş sonrası yönlendirmeyi bekle
            wait.until(EC.url_changes(self.login_url))

            if "login/index.php" not in self.driver.current_url:
                print(f"Giriş başarılı! Yönlendirilen URL: {self.driver.current_url}")
                self.dashboard_url = self.driver.current_url
                return True
            else:
                print("Giriş başarısız oldu.")
                return False

        except (TimeoutException, NoSuchElementException) as e:
            print(f"Giriş sırasında bir element bulunamadı veya zaman aşımı: {e}")
            return False
        except Exception as e:
            print(f"Girişte beklenmedik bir hata oluştu: {e}")
            return False

    def get_language_level_links(self):
        """
        Anasayfadan "Lisan Eğitim Portalı" altındaki dil ve seviye linklerini (örn: Almanca A1) çeker.
        """
        if not self.driver:
            print("Hata: WebDriver başlatılmamış veya giriş yapılmamış.")
            return {}

        # Dashboard'a giderek sayfanın doğru yüklendiğinden emin ol
        print(f"Dashboard URL'ine gidiliyor: {self.dashboard_url}")
        self.driver.get(self.dashboard_url) 
        time.sleep(3) # Sayfanın tamamen yüklenmesi için bekle

        print("\nDil seviyeleri linkleri çekiliyor...")
        language_levels = {}

        try:
            # "LİSAN EĞİTİM PORTALI" düğmesini bul ve tıklanabilir olana kadar bekle
            print("Lisan Eğitim Portalı butonunu arıyorum (ID: activates-tab)...")
            language_portal_button = WebDriverWait(self.driver, 60).until(
                EC.element_to_be_clickable((By.ID, "activates-tab"))
            )
            print(f"Lisan Eğitim Portalı butonu bulundu: '{language_portal_button.text}'")

            # Eğer zaten aktif değilse tıkla
            if "active" not in language_portal_button.get_attribute("class"):
                print("Lisan Eğitim Portalı butonu aktif değil, tıklıyorum...")
                language_portal_button.click()
                time.sleep(3) # Akordiyonun açılması için biraz daha bekle

            print("Dil kartlarını arıyorum (.tab-pane.active .faq-card)...")
            faq_cards = self.driver.find_elements(By.CSS_SELECTOR, ".tab-pane.active .faq-card")
            if not faq_cards:
                print("Hata: 'Lisan Eğitim Portalı' altında hiç dil kartı bulunamadı.")
                print("Mevcut sayfa başlığı:", self.driver.title)
                print("Sayfa kaynağının bir kısmı (hata ayıklama için):", self.driver.page_source[:1000])
                return {}
            print(f"Toplam {len(faq_cards)} adet dil kartı bulundu.")
            
            for i, card in enumerate(faq_cards):
                try:
                    lang_heading = card.find_element(By.CSS_SELECTOR, ".card-heading span a")
                    language_name = lang_heading.text.strip()
                    print(f"  Dil: {language_name}")
                    
                    language_levels[language_name] = {}

                    # Dilin seviyelerini gösteren akordiyonu aç
                    card_heading_element = card.find_element(By.CLASS_NAME, "card-heading")
                    if "collapsed" in card_heading_element.get_attribute("class"):
                        print(f"    '{language_name}' akordiyonunu açıyorum (tıklama)...")
                        self.driver.execute_script("arguments[0].click();", card_heading_element)
                        time.sleep(2) # Açılmasını bekle

                    # Açılan akordiyondaki seviye linklerini bul
                    level_links_container = card.find_element(By.CLASS_NAME, "faq-card-body")
                    level_list_items = level_links_container.find_elements(By.TAG_NAME, "li")
                    
                    if not level_list_items:
                        print(f"    Uyarı: '{language_name}' altında hiç seviye linki bulunamadı. Atlanıyor.")
                        continue

                    for item in level_list_items:
                        level_anchor = item.find_element(By.TAG_NAME, "a")
                        level_name = level_anchor.text.strip()
                        level_url = level_anchor.get_attribute("href")
                        language_levels[language_name][level_name] = level_url
                        # print(f"      - Seviye: {level_name}, URL: {level_url}")

                except NoSuchElementException:
                    print(f"  Uyarı: Kart {i+1} ({language_name if 'language_name' in locals() else 'Bilinmeyen'}) içinde beklenen bir element bulunamadı. Atlanıyor.")
                except Exception as e:
                    print(f"  Bir dil kartı işlenirken beklenmedik hata oluştu ({language_name if 'language_name' in locals() else 'Bilinmiyor'}): {e}")
                    continue

        except TimeoutException:
            print("Zaman aşımı: 'Lisan Eğitim Portalı' butonu veya dil kartları beklenen sürede bulunamadı.")
            print("Mevcut sayfa başlığı:", self.driver.title)
            print("Sayfa kaynağının bir kısmı (hata ayıklama için):", self.driver.page_source[:1000])
        except Exception as e:
            print(f"Dil seviyeleri linkleri çekilirken genel hata oluştu: {e}")
            
        return language_levels

    def scrape_doyk_content(self, url):
        """
        (Yeni) Kurs kartlarını liste sayfasından al, sonra tüm kursları
        tam gezinmeden fetch+DOMParser ile say.
        """
        if not self.driver:
            print("Hata: WebDriver başlatılmamış.")
            return None

        print(f"\nKurs listesi için sayfaya gidiliyor: {url}")
        self.driver.get(url)

        wait = WebDriverWait(self.driver, 60)
        # Sayfa tam yüklenmesini beklemeyelim; kartların geldiğini görmek yeterli
        try:
            wait.until(lambda d: d.execute_script('return document.readyState') in ('interactive','complete'))
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".course-cards .card-wrapper")))
        except TimeoutException:
            print("Kurs kartları görünmedi, atlanıyor.")
            return []

        # Liste sayfasında JS ile kurs linklerini al
        course_cards = self.driver.execute_script("""
            const cards = document.querySelectorAll('.course-cards .card-wrapper');
            const info = [];
            cards.forEach(card => {
                const a = card.querySelector('.coursename');
                if (a && a.href) info.push({title: a.innerText.trim(), url: a.href});
            });
            return info;
        """) or []

        if not course_cards:
            print("Uyarı: Kurs kartı bulunamadı.")
            return []

        print(f"Toplam {len(course_cards)} kurs bulundu. Fetch ile sayılıyor...")
        # Tam gezinmeden, sadece HTML çek
        counted = self.fetch_course_counts_bulk(course_cards, timeout_sec=180, concurrency=6)

        # Dönüş formatını eski kodla uyumlu hale getir
        all_courses_with_js_counts = []
        for c in counted:
            all_courses_with_js_counts.append({
                "title": c.get("title", ""),
                "url": c.get("url"),
                "total_resources_from_js": c.get("total", 0)
            })
        return all_courses_with_js_counts

    def fetch_course_counts_bulk(self, courses, timeout_sec=120, concurrency=5):
            """
            Aynı domain içindeki course URL'lerini tam gezinmeden, sadece HTML getirerek sayar.
            courses: [{'title':..., 'url':...}, ...]
            Dönüş: [{'title':..., 'url':..., 'total': int}, ...]
            """
            # execute_async_script ile tarayıcı içinde fetch + DOMParser çalıştır
            js = """
                const courses = arguments[0];
                const concurrency = arguments[1] || 5;
                const callback = arguments[arguments.length - 1];

                const worker = async (items) => {
                    const results = [];
                    for (const it of items) {
                        try {
                            const r = await fetch(it.url, { credentials: 'include' });
                            const html = await r.text();
                            // Dış kaynaklar yüklenmez; sadece metin.
                            const doc = new DOMParser().parseFromString(html, 'text/html');

                            const h5pDivs   = doc.querySelectorAll('div.h5p-placeholder:not(:has(div.hiddenactivity))').length;
                            const resources = doc.querySelectorAll('li.resource:not(:has(div.hiddenactivity))').length;
                            const h5pLis    = doc.querySelectorAll('li.h5pactivity:not(:has(div.hiddenactivity))').length;
                            const assigns   = doc.querySelectorAll('li.modtype_assign:not(:has(div.hiddenactivity))').length;
                            const videos    = doc.querySelectorAll('div.video-js:has(video):not(:has(audio)):not(:has(.hiddenactivity))').length;


                            const total = h5pDivs + resources + h5pLis + assigns + videos;
                            results.push({ title: it.title || '', url: it.url, total });
                        } catch(e) {
                            results.push({ title: it.title || '', url: it.url, total: 0, error: String(e) });
                        }
                    }
                    return results;
                };

                (async () => {
                    const buckets = [];
                    for (let i = 0; i < courses.length; i += concurrency) {
                        buckets.push(courses.slice(i, i + concurrency));
                    }

                    const out = [];
                    for (const b of buckets) {
                        const chunk = await worker(b);
                        out.push(...chunk);
                    }
                    callback(out);
                })();
            """
            try:
                WebDriverWait(self.driver, timeout_sec).until(
                    lambda d: d.execute_script('return document.readyState') in ('interactive','complete')
                )
                results = self.driver.execute_async_script(js, courses, concurrency)
                return results
            except Exception as e:
                print("fetch_course_counts_bulk hatası:", e)
                return []


    def close_driver(self):
        """WebDriver'ı kapatır."""
        if self.driver:
            print("WebDriver kapatılıyor.")

            self.driver.quit()
