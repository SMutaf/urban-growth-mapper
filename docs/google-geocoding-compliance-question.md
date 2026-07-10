# Google Geocoding API Kullanım Şartları Uygunluk Sorusu

## Bağlam

Sakarya ili için bir şehir büyüme aksı / arsa değerleme platformu geliştiriyoruz.
Platformun temel haritası **OpenStreetMap** (Leaflet + `tile.openstreetmap.org`) —
Google Maps kullanmıyoruz ve kullanmayı planlamıyoruz.

Elimizde Sakarya Büyükşehir Belediyesi'nin resmi açık veri portalından
(`veri.sakarya.bel.tr`) indirdiğimiz, il genelindeki **686 devlet/özel okulun**
adını, ilçesini ve düz metin (sokak/mahalle) adresini içeren bir Excel dosyası
var. Bu dosyada GPS koordinatı **yok**.

## Planladığımız kullanım

1. Bu 686 adresi, **tek seferlik bir toplu işlemle**, Google Geocoding API'ye
   göndererek her biri için enlem/boylam almak.
2. Elde edilen koordinatları **kendi PostgreSQL/PostGIS veritabanımıza** kalıcı
   olarak kaydetmek.
3. Bu koordinatları, kendi **OpenStreetMap tabanlı** haritamızda, platformu
   ziyaret eden **tüm kullanıcılara** göstermek — Google'ın API'sine tekrar
   sorgu atmadan, kendi veritabanımızdan sürekli.
4. Veri kaynağı (belediyenin Excel dosyası) güncellendiğinde (örn. yeni bir
   okul açıldığında) sadece o zaman yeniden geocode etmek; aksi halde tekrar
   sorgu atmamak.

## Emin olamadığımız nokta

Google Geocoding API politikaları şu istisnayı tanımlıyor:

> "You may temporarily cache latitude and longitude values from the Geocoding
> API for up to 30 consecutive calendar days... [veya] indefinitely cache
> latitude, longitude, formatted_address, and structured address values...
> solely to support the direct, End User facing functionality of the Customer
> Application that initiated the request... **Cached data must be logically
> isolated to the specific End User it is associated with and must not be
> used across multiple End Users.**"

Bizim senaryomuzda:
- Koordinatlar **30 günden çok daha uzun süre** (aslında süresiz) saklanacak.
- Koordinatları ilk isteği yapan **tek bir kullanıcıya özel değil**,
  platformu ziyaret eden **herkese** göstereceğiz — yani "multiple End
  Users" arasında paylaşılan bir kullanım.

## Sorumuz

Yukarıdaki senaryo (bir kurumsal/kamu veri kaynağından gelen 686 adresin
Geocoding API ile bir kez koordinatlandırılıp, sonucun kendi veritabanımızda
kalıcı olarak saklanarak tüm son kullanıcılara gösterilmesi):

1. Geocoding API'nin "tek kullanıcıya özel önbellekleme" istisnasının dışında
   mı kalıyor, yani genel şartlardaki 30 günlük geçici önbellekleme sınırına
   mı tabi?
2. Bu kullanım için ayrı bir lisans/anlaşma (örn. Google Maps Platform'un
   kurumsal/Places Data lisanslama seçenekleri) mi gerekiyor?
3. Küçük ölçekli (686 kayıt), ticari olmayan bir prototip/MVP için bu tür bir
   kullanım pratikte kabul edilebilir mi, yoksa ölçekten bağımsız olarak
   şartlara aykırı mı sayılıyor?
