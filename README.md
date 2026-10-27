# bizhub215-linux-driver

[![Tests](https://github.com/Redgion/bizhub215-linux-driver/actions/workflows/test.yml/badge.svg)](https://github.com/Redgion/bizhub215-linux-driver/actions/workflows/test.yml)
[![Release](https://img.shields.io/github/v/release/Redgion/bizhub215-linux-driver)](https://github.com/Redgion/bizhub215-linux-driver/releases/latest)
[![License: GPL v2+](https://img.shields.io/badge/license-GPL--2.0--or--later-blue)](LICENSE)

**Печать и сканирование на Konica Minolta bizhub 215 из Linux, без Windows и Wine.**

Открытый CUPS-фильтр для GDI/JBIG-печати по сети. Реальная печать и работа
через KDE/CUPS подтверждены на Fedora 44 x86_64. Неофициальный проект,
не связанный с Konica Minolta. Windows-драйвер и его DLL не распространяются.

## Скачать и установить

1. Откройте [последний релиз](https://github.com/Redgion/bizhub215-linux-driver/releases/latest).
2. Скачайте `bizhub215-linux-driver-0.4.0.tar.gz` или `.zip`, распакуйте.
3. В папке проекта выполните **обычным пользователем**:

```sh
sh install.sh --setup --printer 192.0.2.10
```

Замените `192.0.2.10` на IP своего МФУ. Установщик предложит установить
зависимости из репозитория дистрибутива, соберёт кодировщик под ваш процессор,
запустит тесты и запросит подтверждение системной установки. Затем предложит
создать отдельную очередь `Konica_215_Custom`. Тестовую печать не запускает.

Без `--printer` устанавливаются только файлы драйвера. Обычный запуск
`sh install.sh` показывает информацию без изменений системы. Не выполняйте
`sudo sh install.sh --setup`: сборка выполняется без root, привилегии
запрашиваются только для установки пакетов, файлов и очереди.

Если в релизе есть `.rpm` или `.deb`, он предназначен только для указанной
в имени платформы. Универсальный вариант — архив исходников с `--setup`.

## Совместимость

| Система | Установка | Уровень подтверждения |
|---|---|---|
| Fedora 44, x86_64 | dnf / исходники | Физическая печать и KDE/CUPS проверены |
| Ubuntu / Debian / Mint | apt / исходники | Подготовлена установка; смотрите результаты CI |
| Arch / Manjaro | pacman / исходники | Подготовлен список зависимостей; аппаратно не проверено |
| openSUSE | zypper / исходники | Подготовлен список зависимостей; аппаратно не проверено |
| Другие Linux | Ручная установка зависимостей | Возможна при выполнении требований ниже |

Требуются **CUPS 2.x, Python ≥3.8, Ghostscript, GCC/совместимый C-компилятор,
make и JBIG-KIT с заголовками**. CUPS 3, Windows, macOS и неизменяемые системы
без совместимого системного CUPS не поддерживаются этим установщиком.
Исходники не привязаны к x86_64; другие архитектуры аппаратно не проверены.
Гарантировать работу на буквально любом Linux было бы неверно.

## Возможности и ограничения

- A4, чёрно-белая печать, 600 dpi, портретная ориентация, одна копия.
- PDF до 200 страниц и 64 MiB; готовое задание также до 64 MiB.
  Обработка ограничена 60 секундами; страницы вписываются в A4.
- Несколько страниц локально проверены; отдельного подтверждения двух
  физических листов пока нет.
- Дуплекс, несколько копий, диапазон страниц, N-up и принудительный альбомный
  режим пока отвергаются с понятной ошибкой.
- Печать по сетевому RAW TCP 9100. USB и другие модели не проверены.
- Источник бумаги выбирается автоматически; точные аппаратные поля не измерены.

Принтер получает постоянное `USERNAME=linux`. Имя пользователя CUPS,
название документа и имя компьютера в печатный поток не добавляются.
Сам CUPS и принтер могут вести собственные журналы — драйвер их не очищает.

## Сборка и локальная проверка

```sh
make test
python3 tools/km215_job.py --pdf document.pdf document.prn
```

Эта команда создаёт файл и ничего не отправляет на принтер. Существующий
выходной файл не перезаписывается. Успешный статус CUPS/TCP сам по себе
не означает физическую печать.

## Сканер

Добавлена поддержка сетевого сканирования через открытый SANE-backend с профилем
bizhub 215. Два настоящих скана A4/150 dpi (Gray и Color) получены на Fedora 44;
Skanpage видит сканер и настройки. Windows DLL для работы не нужны.
WSD у проверенного аппарата возвращает пустое изображение, поэтому применяется
native TCP 4567. USB, ADF, дуплекс, A3 и 300 dpi аппаратно не подтверждены.

```sh
sh install.sh --setup-scanner --printer 192.0.2.10
```

Запускайте обычным пользователем. Нужны `cc`, `make`, `patch`, `pkg-config`,
`scanimage` и Skanpage либо simple-scan из репозитория дистрибутива.
Установщик с подтверждением загрузит проверенные по SHA-256 исходники SANE,
соберёт отдельную библиотеку и добавит **«Сканер bizhub 215»** в меню.
Системные SANE-библиотеки и CUPS не заменяются; сканирование само не запускается.
[Подробности и удаление профиля](docs/SCANNER.md).

## Безопасность установки и удаление

Установщик не заменяет системные библиотеки и чужие фильтры, не отключает
SELinux, не меняет принтер по умолчанию и существующие очереди. Если свои
целевые файлы уже существуют, установка прекращается. Очередь создаётся
с `abort-job`, без общего доступа. Драйвер не поддерживает автоматический
переход между версиями: сначала удалите старые файлы после проверки очереди.

Удаление собственных файлов (очередь сохраняется):

```sh
sudo sh uninstall.sh
```

Если очередь больше не нужна, сначала убедитесь, что в ней нет ожидающих
заданий, затем удалите только её: `sudo lpadmin -x Konica_215_Custom`.
Для RPM/DEB используйте удаление через пакетный менеджер вместо скрипта.

[Подробная установка](docs/INSTALL.md) · [Протокол](docs/PROTOCOL.md) ·
[Изменения](CHANGELOG.md) · [Сообщить о проблеме](https://github.com/Redgion/bizhub215-linux-driver/issues/new/choose)

## English

Unofficial open-source Konica Minolta bizhub 215 GDI/JBIG printing filter for
CUPS 2.x. Actual A4 monochrome printing and KDE/CUPS use were confirmed on
Fedora 44 x86_64. Download a source release and run
`sh install.sh --setup --printer YOUR_PRINTER_IP` as a regular user.
Dependencies are installed only with confirmation. No Windows DLLs or Wine
are needed. Other distributions and architectures require verification;
CUPS 3, duplex printing and multiple copies are not supported.
Optional native network scanning is available;
see [scanner setup](docs/SCANNER.md) for the verified scope.

## License

GPL-2.0-or-later. The native codec links to the distribution's JBIG-KIT.
See [LICENSE](LICENSE) and [NOTICE](NOTICE). No vendor binaries are included.
The license applies to this implementation; it is not permission to redistribute
or reverse engineer vendor software. See [provenance and legal limits](docs/LICENSING.md)
and [security and privacy](docs/SECURITY.md).
