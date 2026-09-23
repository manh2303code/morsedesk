<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE TS>
<TS version="2.1" language="ru_RU">
<context>
    <name>AboutPage</name>
    <message>
        <location filename="../about_page.py" line="208" />
        <source>Turns Morse code audio into text in English, Russian and Kazakh, and text back into Morse. Nothing leaves this computer.</source>
        <translation>Превращает звук азбуки Морзе в текст на английском, русском и казахском языках, а текст — обратно в сигналы Морзе. Ничто не покидает этот компьютер.</translation>
    </message>
    <message>
        <location filename="../about_page.py" line="211" />
        <source>Technical documentation</source>
        <translation>Техническая документация</translation>
    </message>
    <message>
        <location filename="../about_page.py" line="212" />
        <source>Version {app}, acoustic model {model}</source>
        <translation>Версия {app}, акустическая модель {model}</translation>
    </message>
</context>
<context>
    <name>BusyOverlay</name>
    <message>
        <location filename="../widgets/busy_overlay.py" line="76" />
        <location filename="../widgets/busy_overlay.py" line="82" />
        <location filename="../widgets/busy_overlay.py" line="91" />
        <source>Reading the signal…</source>
        <translation>Чтение сигнала…</translation>
    </message>
    <message>
        <location filename="../widgets/busy_overlay.py" line="84" />
        <source>Choosing the most likely text with the language model…</source>
        <translation>Языковая модель выбирает наиболее вероятный текст…</translation>
    </message>
    <message>
        <location filename="../widgets/busy_overlay.py" line="86" />
        <source>Finishing…</source>
        <translation>Завершение…</translation>
    </message>
    <message>
        <location filename="../widgets/busy_overlay.py" line="89" />
        <source>The result appears when the language model has finished.</source>
        <translation>Результат появится, когда языковая модель закончит работу.</translation>
    </message>
</context>
<context>
    <name>DecodePage</name>
    <message>
        <location filename="../decode_page.py" line="342" />
        <source>Hide plain text</source>
        <translation>Скрыть простой текст</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="342" />
        <source>Show plain text</source>
        <translation>Показать простой текст</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="343" />
        <source>Plain text to select and copy, and the alternative result</source>
        <translation>Простой текст для выделения и копирования, а также альтернативный результат</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="405" />
        <location filename="../decode_page.py" line="753" />
        <source>Open audio file</source>
        <translation>Открыть аудиофайл</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="407" />
        <source>Audio files ({exts})</source>
        <translation>Аудиофайлы ({exts})</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="516" />
        <source>Cannot load audio for playback: {detail}</source>
        <translation>Не удалось загрузить звук для воспроизведения: {detail}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="545" />
        <source>{tone} Hz ± 250 Hz</source>
        <translation>{tone} Гц ± 250 Гц</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="589" />
        <source>Model result: {text}</source>
        <translation>Результат модели: {text}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="590" />
        <source>DSP fallback result: {text}</source>
        <translation>Резервный результат DSP: {text}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="601" />
        <source>No Morse signal found in this audio.</source>
        <translation>В этом аудио не найден сигнал Морзе.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="603" />
        <source>Tone not detected clearly; guessing from the spectral peak, so the result may be wrong.</source>
        <translation>Тон определён нечётко; берётся пик спектра, поэтому результат может быть неверным.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="606" />
        <source>A second tone was found at {second_hz:.0f} Hz; tracking {tracked_hz:.0f} Hz.</source>
        <translation>Обнаружен второй тон на {second_hz:.0f} Гц; отслеживается {tracked_hz:.0f} Гц.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="608" />
        <source>Low confidence.</source>
        <translation>Низкая уверенность.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="610" />
        <source>Low confidence; the DSP decoder result is shown too.</source>
        <translation>Низкая уверенность; показан также результат DSP-декодера.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="628" />
        <source>File not found: {path}</source>
        <translation>Файл не найден: {path}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="630" />
        <source>Cannot read {path}. Supported formats: {exts}</source>
        <translation>Не удалось прочитать {path}. Поддерживаемые форматы: {exts}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="634" />
        <source>{path} is {minutes} min long; this version supports up to {limit} min.</source>
        <translation>Длительность {path} — {minutes} мин; эта версия поддерживает до {limit} мин.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="636" />
        <source>Setup problem: a model or language model file is missing or unusable.</source>
        <translation>Проблема установки: файл модели или языковой модели отсутствует либо непригоден.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="637" />
        <source>Internal error while decoding. See the log file for details.</source>
        <translation>Внутренняя ошибка при декодировании. Подробности в файле журнала.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="704" />
        <source>Decoding cancelled.</source>
        <translation>Декодирование отменено.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="721" />
        <source>Text files (*.txt)</source>
        <translation>Текстовые файлы (*.txt)</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="721" />
        <source>JSON files (*.json)</source>
        <translation>Файлы JSON (*.json)</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="722" />
        <location filename="../decode_page.py" line="771" />
        <source>Export</source>
        <translation>Экспорт</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="736" />
        <source>Cannot write {path}: {detail}</source>
        <translation>Не удалось записать {path}: {detail}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="752" />
        <source>Open audio file… (Ctrl+O)</source>
        <translation>Открыть аудиофайл… (Ctrl+O)</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="770" />
        <source>Export to a file: text or JSON with timings</source>
        <translation>Экспорт в файл: текст или JSON с временными метками</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="772" />
        <source>Text file (.txt)…</source>
        <translation>Текстовый файл (.txt)…</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="773" />
        <source>JSON with word timings (.json)…</source>
        <translation>JSON с временем каждого слова (.json)…</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="774" />
        <source>Decoded text</source>
        <translation>Расшифрованный текст</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="754" />
        <source>Message language:</source>
        <translation>Язык сообщения:</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="756" />
        <source>Auto</source>
        <translation>Авто</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="757" />
        <location filename="../decode_page.py" line="784" />
        <source>English</source>
        <translation>Английский</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="758" />
        <location filename="../decode_page.py" line="784" />
        <source>Russian</source>
        <translation>Русский</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="759" />
        <location filename="../decode_page.py" line="784" />
        <source>Kazakh</source>
        <translation>Казахский</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="763" />
        <source>Use language model</source>
        <translation>Использовать языковую модель</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="764" />
        <source>Auto always uses the language model.</source>
        <translation>Режим «Авто» всегда использует языковую модель.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="766" />
        <source>Decode</source>
        <translation>Декодирование</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="767" />
        <source>Cancel</source>
        <translation>Отмена</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="768" />
        <source>Copy the decoded text</source>
        <translation>Копировать расшифрованный текст</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="769" />
        <source>Copy</source>
        <translation>Копировать</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="777" />
        <source>No file selected. Drop an audio file here.</source>
        <translation>Файл не выбран. Перетащите аудиофайл сюда.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="778" />
        <source>Sample</source>
        <translation>Пример</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="779" />
        <source>Signal</source>
        <translation>Сигнал</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="780" />
        <source>3D</source>
        <translation>3D</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="781" />
        <source>Spectrogram</source>
        <translation>Спектрограмма</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="782" />
        <source>Open or drop an audio file to see its signal in 3D.</source>
        <translation>Откройте или перетащите аудиофайл, чтобы увидеть его сигнал в 3D.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="783" />
        <source>Read as:</source>
        <translation>Читать как:</translation>
    </message>
</context>
<context>
    <name>EncodePage</name>
    <message>
        <location filename="../encode_page.py" line="357" />
        <source>Estimated audio is {minutes} min long; the limit is {limit} min. Shorten the text or raise the speed.</source>
        <translation>Расчётная длительность аудио {minutes} мин, предел {limit} мин. Сократите текст или увеличьте скорость.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="427" />
        <source>Invalid timing settings: the Farnsworth speed must not exceed the speed in WPM.</source>
        <translation>Неверные параметры тайминга: скорость Фарнсворта не должна превышать скорость в WPM.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="430" />
        <source>Could not build the audio.</source>
        <translation>Не удалось построить аудио.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="451" />
        <source>Save audio</source>
        <translation>Сохранить аудио</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="451" />
        <source>Audio ({ext})</source>
        <translation>Аудио ({ext})</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="477" />
        <source>Cannot write {path}: {detail}</source>
        <translation>Не удалось записать {path}: {detail}</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="486" />
        <source>Text to encode</source>
        <translation>Текст для кодирования</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="487" />
        <source>Morse code:</source>
        <translation>Код Морзе:</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="492" />
        <source>Type text to see its Morse code.</source>
        <translation>Введите текст, чтобы увидеть код Морзе.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="276" />
        <location filename="../encode_page.py" line="493" />
        <source>English</source>
        <translation>Английский</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="276" />
        <location filename="../encode_page.py" line="494" />
        <source>Russian</source>
        <translation>Русский</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="276" />
        <location filename="../encode_page.py" line="494" />
        <source>Kazakh</source>
        <translation>Казахский</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="278" />
        <source>Detected alphabet: {name}</source>
        <translation>Определённый алфавит: {name}</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="303" />
        <location filename="../encode_page.py" line="421" />
        <source>Cannot encode {chars} — fix the text or switch alphabet before sending.</source>
        <translation>Невозможно закодировать {chars} — исправьте текст или смените алфавит перед передачей.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="342" />
        <source>Length ≈ {t}</source>
        <translation>Длительность ≈ {t}</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="488" />
        <source>The message appears here as signal-lamp marks.</source>
        <translation>Здесь сообщение появится в виде сигнальных огней.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="489" />
        <source>Alphabet</source>
        <translation>Алфавит</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="489" />
        <source>Timing</source>
        <translation>Тайминг</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="490" />
        <source>Sound</source>
        <translation>Звук</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="490" />
        <source>File</source>
        <translation>Файл</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="493" />
        <source>Auto</source>
        <translation>Авто</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="501" />
        <source>Profile:</source>
        <translation>Профиль:</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="502" />
        <source>Speed (WPM):</source>
        <translation>Скорость (WPM):</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="503" />
        <source>Farnsworth (WPM):</source>
        <translation>Фарнсворт (WPM):</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="504" />
        <source>Weight:</source>
        <translation>Вес:</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="505" />
        <source>Tone (Hz):</source>
        <translation>Тон (Гц):</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="506" />
        <source>Add noise, SNR (dB):</source>
        <translation>Добавить шум, ОСШ (дБ):</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="507" />
        <source>Format:</source>
        <translation>Формат:</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="512" />
        <source>Play</source>
        <translation>Воспроизвести</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="513" />
        <source>Stop</source>
        <translation>Стоп</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="514" />
        <source>Save…</source>
        <translation>Сохранить…</translation>
    </message>
</context>
<context>
    <name>LivePage</name>
    <message>
        <location filename="../live_page.py" line="181" />
        <source>No input device found. Plug in a sound card or check that PortAudio is installed.</source>
        <translation>Устройство ввода не найдено. Подключите звуковую карту или проверьте установку PortAudio.</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="206" />
        <source>Hz</source>
        <translation>Гц</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="206" />
        <source>dB</source>
        <translation>дБ</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="206" />
        <source>WPM</source>
        <translation>WPM</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="206" />
        <source>s</source>
        <translation>с</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="211" />
        <location filename="../live_page.py" line="298" />
        <source>English</source>
        <translation>Английский</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="211" />
        <location filename="../live_page.py" line="298" />
        <source>Russian</source>
        <translation>Русский</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="211" />
        <location filename="../live_page.py" line="299" />
        <source>Kazakh</source>
        <translation>Казахский</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="220" />
        <source>WPM {v:.1f}</source>
        <translation>Слов/мин {v:.1f}</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="222" />
        <source>Tone {v:.0f} Hz</source>
        <translation>Тон {v:.0f} Гц</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="224" />
        <source>SNR {v:.1f} dB</source>
        <translation>ОСШ {v:.1f} дБ</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="227" />
        <source>Alphabet: {v}</source>
        <translation>Алфавит: {v}</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="228" />
        <source>{v:.0f} s heard</source>
        <translation>принято {v:.0f} с</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="243" />
        <source>Listening failed: {detail}</source>
        <translation>Не удалось вести приём: {detail}</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="293" />
        <source>Input:</source>
        <translation>Вход:</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="294" />
        <source>Alphabet:</source>
        <translation>Алфавит:</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="296" />
        <source>Auto detects the alphabet from the message itself</source>
        <translation>«Авто» определяет алфавит по самому сообщению</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="297" />
        <source>Refresh</source>
        <translation>Обновить</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="298" />
        <source>Auto</source>
        <translation>Авто</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="302" />
        <source>Look for newly plugged devices</source>
        <translation>Найти недавно подключённые устройства</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="303" />
        <source>Stop</source>
        <translation>Стоп</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="303" />
        <source>Listen</source>
        <translation>Слушать</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="304" />
        <source>Input level</source>
        <translation>Уровень входного сигнала</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="305" />
        <source>Level</source>
        <translation>Уровень</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="306" />
        <source>Alphabet</source>
        <translation>Алфавит</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="307" />
        <source>Tone</source>
        <translation>Тон</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="308" />
        <source>Speed</source>
        <translation>Скорость</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="309" />
        <source>SNR</source>
        <translation>ОСШ</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="310" />
        <source>Heard</source>
        <translation>Принято</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="311" />
        <source>Press Listen to see the band live in 3D.</source>
        <translation>Нажмите «Слушать», чтобы видеть диапазон в 3D в реальном времени.</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="312" />
        <source>0–2000 Hz, newest in front</source>
        <translation>0–2000 Гц, новое — спереди</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="313" />
        <source>Decoded text appears here as it is heard.</source>
        <translation>Декодированный текст появляется здесь по мере приёма.</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="314" />
        <source>Grey text may still change; plain text is final.</source>
        <translation>Серый текст ещё может измениться; обычный текст окончателен.</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="315" />
        <source>Copy the decoded text</source>
        <translation>Копировать расшифрованный текст</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="316" />
        <source>Copy</source>
        <translation>Копировать</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="317" />
        <source>Clear the text and start over</source>
        <translation>Очистить текст и начать заново</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="318" />
        <source>Clear</source>
        <translation>Очистить</translation>
    </message>
</context>
<context>
    <name>MainWindow</name>
    <message>
        <location filename="../main_window.py" line="147" />
        <source>MorseDesk</source>
        <translation>MorseDesk</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="148" />
        <source>UI language:</source>
        <translation>Язык интерфейса:</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="153" />
        <source>Decode</source>
        <translation>Декодирование</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="155" />
        <source>Listen</source>
        <translation>Слушать</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="157" />
        <source>Encode</source>
        <translation>Кодирование</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="159" />
        <source>About</source>
        <translation>О программе</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="161" />
        <source>Settings</source>
        <translation>Настройки</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="200" />
        <source>Finishing the current decode; the window will close right after.</source>
        <translation>Завершается текущее декодирование; окно закроется сразу после этого.</translation>
    </message>
</context>
<context>
    <name>PlayerBar</name>
    <message>
        <location filename="../widgets/player_bar.py" line="221" />
        <source>Pause</source>
        <translation>Пауза</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="221" />
        <source>Play</source>
        <translation>Воспроизвести</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="223" />
        <source>Pause playback</source>
        <translation>Приостановить воспроизведение</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="223" />
        <source>Listen to the decoded audio</source>
        <translation>Прослушать декодированный сигнал</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="224" />
        <source>Drag to jump to a moment</source>
        <translation>Перетащите, чтобы перейти к моменту</translation>
    </message>
</context>
<context>
    <name>SettingsPage</name>
    <message>
        <location filename="../settings_page.py" line="101" />
        <source>MP3 export: available through libsndfile (built-in LAME).</source>
        <translation>Экспорт MP3: доступен через libsndfile (встроенный LAME).</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="103" />
        <source>MP3 export: available through the external ffmpeg command.</source>
        <translation>Экспорт MP3: доступен через внешнюю команду ffmpeg.</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="105" />
        <source>MP3 export: NOT available. libsndfile here has no LAME encoder and ffmpeg is not on PATH; install ffmpeg or export another format.</source>
        <translation>Экспорт MP3: НЕДОСТУПЕН. В libsndfile здесь нет кодера LAME, а ffmpeg отсутствует в PATH; установите ffmpeg или выберите другой формат.</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="112" />
        <source>Decoding engine: {engine}</source>
        <translation>Движок декодирования: {engine}</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="114" />
        <source>Other formats written directly: {exts}</source>
        <translation>Другие форматы записываются напрямую: {exts}</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="115" />
        <source>Log file: {path}</source>
        <translation>Файл журнала: {path}</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="129" />
        <source>version {v}</source>
        <translation>версия {v}</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="131" />
        <source>{n} parameters</source>
        <translation>{n} параметров</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="133" />
        <source>Decoding engine</source>
        <translation>Движок декодирования</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="134" />
        <source>Acoustic model</source>
        <translation>Акустическая модель</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="135" />
        <source>Language models</source>
        <translation>Языковые модели</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="135" />
        <location filename="../settings_page.py" line="138" />
        <source>none found</source>
        <translation>не найдено</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="136" />
        <source>MP3 export</source>
        <translation>Экспорт MP3</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="137" />
        <source>Formats written directly</source>
        <translation>Форматы для прямой записи</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="138" />
        <source>Sound inputs</source>
        <translation>Звуковые входы</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="139" />
        <source>Log file</source>
        <translation>Файл журнала</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="144" />
        <source>Neural network (ONNX) with the classic DSP decoder</source>
        <translation>Нейросеть (ONNX) и классический DSP-декодер</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="145" />
        <source>Classic DSP decoder only</source>
        <translation>Только классический DSP-декодер</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="156" />
        <source>This computer</source>
        <translation>Этот компьютер</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="160" />
        <source>Open log folder</source>
        <translation>Открыть папку журнала</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="161" />
        <source>Copy report</source>
        <translation>Копировать отчёт</translation>
    </message>
</context>
<context>
    <name>SpectrogramView</name>
    <message>
        <location filename="../widgets/spectrogram.py" line="50" />
        <source>s</source>
        <translation>с</translation>
    </message>
    <message>
        <location filename="../widgets/spectrogram.py" line="51" />
        <source>Hz</source>
        <translation>Гц</translation>
    </message>
</context>
<context>
    <name>StatsBar</name>
    <message>
        <location filename="../widgets/stats_bar.py" line="87" />
        <source>English</source>
        <translation>Английский</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="88" />
        <source>Russian</source>
        <translation>Русский</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="89" />
        <source>Kazakh</source>
        <translation>Казахский</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="90" />
        <source>Auto</source>
        <translation>Авто</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="93" />
        <source>not detected</source>
        <translation>не определён</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="126" />
        <source>Language</source>
        <translation>Язык</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="127" />
        <source>Tone</source>
        <translation>Тон</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="128" />
        <source>Speed</source>
        <translation>Скорость</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="129" />
        <source>SNR</source>
        <translation>ОСШ</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="130" />
        <source>Decoded by</source>
        <translation>Декодер</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="131" />
        <source>Took</source>
        <translation>Время</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="134" />
        <source>No result yet.</source>
        <translation>Результата пока нет.</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="141" />
        <source>Hz</source>
        <translation>Гц</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="142" />
        <source>dB</source>
        <translation>дБ</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="143" />
        <source>WPM</source>
        <translation>WPM</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="144" />
        <source>s</source>
        <translation>с</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="149" />
        <source>classic DSP</source>
        <translation>классический DSP</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="149" />
        <source>neural model</source>
        <translation>нейросеть</translation>
    </message>
    <message>
        <location filename="../widgets/stats_bar.py" line="153" />
        <source>{lang} (auto)</source>
        <translation>{lang} (авто)</translation>
    </message>
</context>
<context>
    <name>TechDocWindow</name>
    <message>
        <location filename="../doc_window.py" line="139" />
        <source>MorseDesk technical reference</source>
        <translation>Техническое описание MorseDesk</translation>
    </message>
    <message>
        <location filename="../doc_window.py" line="142" />
        <location filename="../doc_window.py" line="150" />
        <source>Save as PDF…</source>
        <translation>Сохранить как PDF…</translation>
    </message>
    <message>
        <location filename="../doc_window.py" line="151" />
        <source>PDF files (*.pdf)</source>
        <translation>Файлы PDF (*.pdf)</translation>
    </message>
    <message>
        <location filename="../doc_window.py" line="163" />
        <source>Saved {path}</source>
        <translation>Сохранено: {path}</translation>
    </message>
    <message>
        <location filename="../doc_window.py" line="164" />
        <source>Could not save {path}</source>
        <translation>Не удалось сохранить {path}</translation>
    </message>
</context>
<context>
    <name>WordView</name>
    <message>
        <location filename="../widgets/word_view.py" line="303" />
        <source>confidence {conf:.2f} · {start:.2f}–{end:.2f} s</source>
        <translation>уверенность {conf:.2f} · {start:.2f}–{end:.2f} с</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="407" />
        <source>Words appear here as they are heard.</source>
        <translation>Здесь появятся слова по мере приёма.</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="408" />
        <source>Open an audio file to decode.</source>
        <translation>Откройте аудиофайл для декодирования.</translation>
    </message>
</context>
</TS>