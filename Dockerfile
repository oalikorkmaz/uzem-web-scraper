# Resmi ve hafif bir Python 3.9 imajını temel alarak başlıyoruz.
FROM python:3.9-slim

# Konteyner içinde çalışacağımız klasörü belirliyoruz.
WORKDIR /app

# Önce sadece requirements.txt dosyasını kopyalıyoruz.
# Bu sayede, sadece kütüphane listesi değiştiğinde 'pip install' adımı tekrar çalışır, bu da derleme süresini hızlandırır.
COPY requirements.txt .

# requirements.txt içinde listelenen tüm Python kütüphanelerini kuruyoruz.
RUN pip install --no-cache-dir -r requirements.txt

# Projemizdeki diğer tüm dosyaları (.py, .html vb.) konteynerin içine kopyalıyoruz.
COPY . .

# Bu Dockerfile'dan bir konteyner başlatıldığında varsayılan olarak hangi komutun çalışacağını belirtir.
# Biz bunu docker-compose.yml dosyasında ezeceğimiz için bu satır aslında opsiyoneldir.
CMD ["flask", "run", "--host=0.0.0.0"]