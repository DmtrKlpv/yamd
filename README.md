## Получение OAuth-токена Яндекс
Для работы с API необходимо зарегистрировать приложение и получить токен доступа.

1. **Регистрация приложения**: Перейдите на [oauth.yandex.ru](https://oauth.yandex.ru), заполните форму и выберите нужные доступы (например, «Веб-сервисы», «Яндекс Музыка»).
   - **Callback URI**: укажите `https://oauth.yandex.ru/verification_code`.
2. **Получение ID**: После создания приложения скопируйте его `ClientID`.
3. **Переход по ссылке**: Вставьте ваш `ClientID` в следующую ссылку и откройте её в браузере:
   `https://oauth.yandex.ru/authorize?response_type=token&client_id=<ID_ВАШЕГО_ПРИЛОЖЕНИЯ>`
4. **Разрешение доступа**: Нажмите **«Разрешить»** (Allow) в открывшемся окне.
5. **Копирование токена**: Браузер перенаправит вас на страницу, в URL которой после символа `#` будет указан `access_token=...`.

> **Важно**: Полученный токен — это секретный ключ, который нельзя передавать третьим лицам. Он используется в API-запросах в заголовке `Authorization: OAuth <токен>`.
>
> **Примечание**: Если треки скачиваются в качестве 128kbps и длительностью 30 секунд — токен недействителен или у вас отсутствует подписка Яндекс Плюс.

---

## yamd — Загрузчик
Основная утилита для скачивания треков.

### Параметры:
* `-h, --help` — Показать справку.
* `-playlist PLAYLIST` — Путь к `.txt` файлу плейлиста.
* `-dir DIR` — Папка для скачивания.
* `-timeout TIMEOUT` — Таймаут соединения (по умолчанию **15**).
* `-maxtr MAXTR` — Макс. количество попыток (по умолчанию **3**).
* `-flac` — Скачивать в формате **FLAC**, если доступно.

**Пример:**
```bash
yam -playlist 'pls\playlist.txt' -flac -timeout 15 -maxtr 3
```

## plsgen - обработчик плейлистов:
* `-h, --help`      show this help message and exit
* `-file FILE`      Имя файла (сохранится в папку pls)
* `-iframe IFRAME`  Строка iframe. Используйте одинарные кавычки

**Пример:**
```bash
plsgen -file 'playlist.txt' -iframe 'ваш iframe'
```

## plscreate - генератор плейлистов
* `-h, --help`           show this help message and exit
* `-f {m3u,m3u8,pls,xspf,wpl}`, * `--format {m3u,m3u8,pls,xspf,wpl}`
Желаемый формат плейлиста:
* `m3u`   - Классический плейлист (ANSI)
* `m3u8`  - Плейлист UTF-8 (для Foobar2000)
* `pls`   - Плейлист Winamp/другие
* `xspf`  - XML формат (для VLC)
* `wpl`   - Windows Media Player
* `-dir OUTPUT_DIR`, * `--output-dir OUTPUT_DIR`
                        Папка для сохранения плейлистов (по умолчанию: корень библиотеки)

**Пример:** 
```bash
plscreate C:/Music -f m3u8 -dir C:/Playlists
```

## duplsearch - поиск дубликатов
* `-h, --help`           show this help message and exit
* `-dir DIRECTORY`, * `--directory` DIRECTORY
                        Директория для поиска

**Пример:** 
```bash
duplsearch -dir D:\Music
```


## plscreate - генератор плейлистов

скрипт читает названия песен из txt-файла (строка за строкой), ищет совпадения по всей глубине указанной папки и формирует плейлист.

positional arguments:
  * `path`                  Путь к музыке (откуда брать папки)

options:
   * `-h, --help`            show this help message and exit
   * `-f {m3u,m3u8,pls,xspf,wpl}`, * `--format {m3u,m3u8,pls,xspf,wpl}`
   Формат плейлиста:
      * `m3u`   - Классический плейлист (ANSI)
      * `m3u8`  - Плейлист UTF-8 (для Foobar2000)
      * `pls`   - Плейлист Winamp/другие
      * `xspf`  - XML формат (для VLC)
      * `wpl`   - Windows Media Player
      * `-savedir SAVEDIR`      Папка для сохранения плейлистов
   * `-list FROM_LIST`, * `--from-list FROM_LIST`
                        Создать плейлист из текстового файла
   * `-searchdir SEARCHDIR`  Папка для поиска треков (используется с -list)
   * `-mass MASS`            Путь к папке с TXT-файлами для массового создания плейлистов
   * `-abs, --absolute`      Использовать абсолютные пути в плейлисте


Пример создания плейлиста из разных папок:
```bash
plscreate -list favorite_songs.txt -searchdir "d:/Music/Library" -f m3u8 -savedir 'd:/playlists'
```
Создание плейлистов по папкам: 
```bash
Пример: plscreate 'd:/Music/Library' -f xspf
```
Пакетное создание плейлистов:
```bash
plscreate plscreate -mass "d:/Music/txt" -searchdir "d:/Music/Library" -savedir 'd:/playlists'-f m3u8
```
