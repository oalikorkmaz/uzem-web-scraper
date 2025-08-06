# tasks.py
import re
from celery import Celery
import time
import os
from scraper_refactored import UzemScraper 
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Side, PatternFill

celery_app = Celery('tasks', broker='redis://redis:6379/0', backend='redis://redis:6379/0')

def create_excel_report(data, minimum_values, task_id):
    """Verilen dataya göre biçimlendirilmiş bir Excel raporu oluşturur ve kaydeder."""
    output_folder = 'output'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    filename = os.path.join(output_folder, f'{task_id}.xlsx')
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'DOYK Analizi'

    # Stil tanımlamaları
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    center_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    warning_fill = PatternFill(start_color="FFEBEE", end_color="FFEBEE", fill_type="solid")

    # Sütun genişlikleri
    sheet.column_dimensions['A'].width = 15
    sheet.column_dimensions['B'].width = 10
    sheet.column_dimensions['C'].width = 5
    sheet.column_dimensions['D'].width = 5
    sheet.column_dimensions['E'].width = 5
    sheet.column_dimensions['F'].width = 5

    current_row = 1
    for language, levels_data in data.items():
        if not levels_data: continue

        # Her dil bloğundan önce boş satır bırak
        if current_row > 1:
            current_row += 1
        
        # Başlıklar
        sheet.cell(row=current_row, column=3, value="DOYK").alignment = center_align
        sheet.merge_cells(start_row=current_row, start_column=3, end_row=current_row, end_column=6)
        
        header_row = current_row + 1
        sheet.cell(row=header_row, column=1, value="Dil").alignment = center_align
        sheet.cell(row=header_row, column=2, value="Seviye").alignment = center_align
        sheet.cell(row=header_row, column=3, value="D").alignment = center_align
        sheet.cell(row=header_row, column=4, value="O").alignment = center_align
        sheet.cell(row=header_row, column=5, value="Y").alignment = center_align
        sheet.cell(row=header_row, column=6, value="K").alignment = center_align

        for col in range(1, 7):
            sheet.cell(row=current_row, column=col).border = thin_border
            sheet.cell(row=header_row, column=col).border = thin_border

        # Veri satırları
        data_start_row = header_row + 1
        min_value = minimum_values.get(language, 42)

        sorted_levels = sorted(levels_data.keys(), key=lambda k: (k[0], int(k[1:])) if len(k) > 1 and k[1:].isdigit() else (k, 0))

        for i, level_code in enumerate(sorted_levels):
            row_num = data_start_row + i
            doyk_counts = levels_data[level_code]
            
            sheet.cell(row=row_num, column=2, value=level_code).alignment = center_align
            
            col_map = {'D': 3, 'O': 4, 'Y': 5, 'K': 6}
            for skill, col_idx in col_map.items():
                cell = sheet.cell(row=row_num, column=col_idx)
                value = doyk_counts.get(skill, 0)
                cell.value = value
                cell.alignment = center_align
                if value < min_value:
                    cell.fill = warning_fill
            
            for col in range(1, 7):
                sheet.cell(row=row_num, column=col).border = thin_border
        
        # Dil adını birleştir ve ortala
        if len(sorted_levels) > 0:
            end_row = data_start_row + len(sorted_levels) - 1
            sheet.merge_cells(start_row=data_start_row, start_column=1, end_row=end_row, end_column=1)
            lang_cell = sheet.cell(row=data_start_row, column=1)
            lang_cell.value = language
            lang_cell.alignment = center_align

        current_row = data_start_row + len(sorted_levels)
    
    workbook.save(filename)
    return filename

@celery_app.task(bind=True)
def start_scrape_process(self, username, password, minimum_values):
    """Celery'nin ana görevi. Veri çeker, işler, ilerleme bildirir ve Excel oluşturur."""
    def update_status(progress, message):
        self.update_state(state='PROGRESS', meta={'progress': progress, 'log_message': message})
        time.sleep(1)

    scraper = None
    try:
        update_status(10, 'Sistem başlatılıyor...')
        scraper = UzemScraper(username, password)
        
        update_status(15, 'WebDriver bağlanıyor...')
        if not scraper.connect_driver():
            raise Exception("WebDriver başlatılamadı...")

        update_status(20, 'Sisteme giriş yapılıyor...')
        if not scraper.login():
            raise Exception("Giriş başarısız oldu...")
        
        update_status(30, 'Dil seviyesi linkleri çekiliyor...')
        language_data = scraper.get_language_level_links()
        if not language_data:
            raise Exception("Ana sayfadan dil seviyesi linkleri çekilemedi.")

        ### BAŞLANGIÇ: Filtreleme Mantığı Düzeltmesi ###
        
        allowed_levels_config = {
            'İngilizce': ['A1', 'A2', 'B1', 'B2', 'C1'],
            'default': ['A1', 'A2', 'B1']
        }
        
        all_scraped_courses = {}
        
        levels_to_process = []
        for lang, levels in language_data.items():
            target_levels = allowed_levels_config.get(lang, allowed_levels_config['default'])
            for level_name in levels.keys():
                # YENİ EKLENEN KISIM: Seviye kodunu Regex ile arıyoruz.
                match = re.search(r'\b(A1|A2|B1|B2|C1|C2)\b', level_name, re.IGNORECASE)
                level_code = match.group(0).upper() if match else None

                if level_code and level_code in target_levels:
                    levels_to_process.append({'lang': lang, 'level_name': level_name, 'level_url': levels[level_name]})
                else:
                    # Bu log mesajı sayesinde hangi seviyelerin atlandığını görebiliriz.
                    print(f"Atlanıyor: {level_name} (Hedef seviye değil veya seviye kodu bulunamadı)")


        total_levels = len(levels_to_process)
        processed_levels = 0
        
        update_status(40, f'Toplam {total_levels} hedef seviye bulundu. Kurslar taranıyor...')

        for item in levels_to_process:
            lang, level_name, level_url = item['lang'], item['level_name'], item['level_url']

            progress = 40 + int(50 * (processed_levels / total_levels)) if total_levels > 0 else 40
            update_status(progress, f"İşleniyor: {lang} - {level_name}")
            
            if lang not in all_scraped_courses:
                all_scraped_courses[lang] = {}

            courses_in_level = scraper.scrape_doyk_content(level_url)
            if courses_in_level:
                all_scraped_courses[lang][level_name] = courses_in_level
            
            processed_levels += 1
            time.sleep(1)

        ### BİTİŞ: Filtreleme Mantığı Düzeltmesi ###

        update_status(90, 'Veriler işleniyor ve gruplanıyor...')
        
        # ... (fonksiyonun geri kalanı, veri işleme ve excel oluşturma kısımları aynı) ...
        doyk_skill_map = {
            "Dinleme Becerisi": "D", "Okuma Becerisi": "O",
            "Yazma Becerisi": "Y", "Konuşma Becerisi": "K"
        }
        grouped_data_by_language = {}

        for lang_category, levels_dict in all_scraped_courses.items():
            current_language_data = {}
            for level_name, courses_list in levels_dict.items():
                # YENİ EKLENEN KISIM: Seviye kodunu burada da Regex ile bulalım ki Excel'e doğru yazılsın
                match = re.search(r'\b(A1|A2|B1|B2|C1|C2)\b', level_name, re.IGNORECASE)
                current_level_code = match.group(0).upper() if match else level_name
                
                doyk_counts_for_level = {skill_code: 0 for skill_code in doyk_skill_map.values()}

                for course_info in courses_list:
                    course_title = course_info.get('title', '')
                    total_resources = course_info.get('total_resources_from_js', 0)
                    
                    for full_skill_name, skill_code in doyk_skill_map.items():
                        if full_skill_name in course_title:
                            doyk_counts_for_level[skill_code] = total_resources
                            break
                
                current_language_data[current_level_code] = doyk_counts_for_level
            
            if current_language_data:
                grouped_data_by_language[lang_category] = current_language_data

        scraper.close_driver()
        scraper = None

        update_status(95, 'Excel raporu oluşturuluyor...')
        excel_file_path = create_excel_report(grouped_data_by_language, minimum_values, self.request.id)

        return {
            'status': 'SUCCESS',
            'data': grouped_data_by_language,
            'excel_filename': os.path.basename(excel_file_path)
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        self.update_state(state='FAILURE', meta={'progress': 0, 'log_message': str(e)})
        return {'status': 'FAILURE', 'log_message': str(e)}
    finally:
        if scraper and scraper.driver:
            scraper.close_driver()