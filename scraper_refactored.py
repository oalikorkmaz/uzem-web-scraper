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

            # --- YENİ EKLENEN OPTİMİZASYON AYARLARI ---

            # 1. Tarayıcının arka planda yaptığı gereksiz ağ isteklerini kapatıyoruz.
            options.add_argument('--disable-background-networking')
            options.add_argument('--disable-sync')
            options.add_argument('--disable-component-update')
            options.add_argument('--disable-default-apps')
            options.add_argument('--no-pings')
            options.add_argument("--disable-domain-reliability")
            options.add_argument("--disable-features=OptimizationHints,MediaRouter")

            # 2. En büyük bant genişliği tasarrufu: Resimlerin yüklenmesini engelliyoruz.
            # 0: Varsayılan, 1: İzin Ver, 2: Engelle
            prefs = {"profile.managed_default_content_settings.images": 2}
            options.add_experimental_option("prefs", prefs)
            
            # --- OPTİMİZASYON AYARLARI BİTTİ ---

            self.driver = webdriver.Remote(
            command_executor='http://selenium_chrome:4444/wd/hub',
            options=options
            )

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
        Verilen dil seviyesi URL'indeki tüm kursları gezer ve kaynak sayısını çeker.
        İyileştirilmiş bekleme ve hata ayıklama mekanizmaları içerir.
        """
        if not self.driver:
            print("Hata: WebDriver başlatılmamış.")
            return None

        print(f"\nKurs listesini almak için sayfaya gidiliyor: {url}")
        
        try:
            self.driver.get(url)
        except Exception as e:
            print(f"Sayfa yüklenirken hata oluştu: {url} - Hata: {e}")
            return None # Sayfa hiç yüklenemezse boş liste döndür

        wait = WebDriverWait(self.driver, 120) # Bekleme süresi 2 dakika
        all_courses_with_js_counts = []
        
        try:
            # Katman 3: Sayfanın tamamen yüklenmesini bekle
            print("Sayfanın tamamen yüklenmesi bekleniyor (document.readyState)...")
            wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
            print("Sayfa tamamen yüklendi.")

            # Ana içeriğin (kurs kartlarının) yüklenmesini bekle
            print(f"'{url}' adresinde kurs kartlarını (.course-cards .card-wrapper) bekliyorum...")
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".course-cards .card-wrapper")))
            
            # JavaScript ile kurs bilgilerini çekme kısmı
            course_cards_info_from_page = self.driver.execute_script("""
                const cards = document.querySelectorAll('.course-cards .card-wrapper');
                const infoList = [];
                cards.forEach(card => {
                    try {
                        const titleElement = card.querySelector('.coursename');
                        const url = titleElement ? titleElement.href : '';
                        const title = titleElement ? titleElement.innerText.trim() : '';
                        if (url && title) {
                            infoList.push({title: title, url: url});
                        }
                    } catch (e) {
                        console.error('Kart bilgisi çekilemedi:', e);
                    }
                });
                return infoList;
            """)
            
            if not course_cards_info_from_page:
                print(f"Uyarı: {url} adresinde JavaScript ile hiç kurs kartı bilgisi toplanamadı.")
                return []
            
            print(f"Toplam {len(course_cards_info_from_page)} adet kurs kartı bilgisi toplandı. Şimdi her birine gidiyorum...")

            # DÖNGÜNÜN DOLDURULMUŞ HALİ
            for course_info in course_cards_info_from_page:
                course_title = course_info.get("title", "Başlık Yok")
                course_url = course_info.get("url")

                if not course_url:
                    continue

                print(f"    --> Kurs detay sayfasına gidiliyor: {course_title}")
                self.driver.get(course_url)
                wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')

                total_count = 0
                try:
                    js_code = """
                        const divCount = document.querySelectorAll('div.h5p-placeholder:not(:has(div.hiddenactivity))').length;
                        const resourceCount = document.querySelectorAll('li.resource:not(:has(div.hiddenactivity))').length;
                        const liCount = document.querySelectorAll('li.h5pactivity:not(:has(div.hiddenactivity))').length;
                        const assignCount = document.querySelectorAll('li.modtype_assign:not(:has(div.hiddenactivity))').length;
                        return divCount + liCount + resourceCount + assignCount;
                       """
                    total_count = self.driver.execute_script(js_code)
                    print(f"    '{course_title}' için kaynak sayısı: {total_count}")
                except Exception as js_e: 
                    print(f"    JavaScript kodu çalıştırılırken hata oluştu: {js_e}")

                combined_course_data = {
                    "title": course_title,
                    "url": course_url,
                    "total_resources_from_js": total_count
                }
                all_courses_with_js_counts.append(combined_course_data)
                time.sleep(1) # Her kurs arası 1 saniye bekle
            
        except TimeoutException:
            print(f"ZAMAN AŞIMI: '{url}' adresinde kurs kartları 120 saniye içinde bulunamadı.")
            print("Sayfanın o anki görüntüsü 'debug_screenshot.png' olarak kaydediliyor.")
            print("Sayfanın HTML kaynağı 'debug_page_source.html' olarak kaydediliyor.")
            
            self.driver.save_screenshot('debug_screenshot.png')
            with open('debug_page_source.html', 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
                
            print("Hata ayıklama dosyaları oluşturuldu.")
            
        except Exception as e:
            print(f"Kurs listesi çekilirken beklenmedik bir genel hata oluştu: {e}")
            
        return all_courses_with_js_counts

    def close_driver(self):
        """WebDriver'ı kapatır."""
        if self.driver:
            print("WebDriver kapatılıyor.")
            self.driver.quit()