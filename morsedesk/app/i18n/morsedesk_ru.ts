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
    <name>AudioText</name>
    <message>
        <location filename="../audio_text.py" line="16" />
        <source>The sound device is not responding (the system audio service or the sound driver is stuck). Playback and listening are paused; everything else keeps working. If sound does not come back within a minute or two, restart the computer.</source>
        <translation>Звуковое устройство не отвечает (зависла системная аудиослужба или звуковой драйвер). Воспроизведение и приём приостановлены; всё остальное работает. Если звук не вернётся через минуту-две, перезагрузите компьютер.</translation>
    </message>
    <message>
        <location filename="../audio_text.py" line="19" />
        <source>Listening is on. Stop listening before playing: the microphone would pick up the speaker.</source>
        <translation>Идёт приём. Остановите приём перед воспроизведением: микрофон уловит звук из динамика.</translation>
    </message>
    <message>
        <location filename="../audio_text.py" line="30" />
        <source>No sound output on this computer: check that a sound card is present and that PortAudio (libportaudio2) is installed. Decoding files still works.</source>
        <translation>На этом компьютере нет вывода звука: проверьте, что звуковая карта есть и PortAudio (libportaudio2) установлен. Декодирование файлов работает.</translation>
    </message>
    <message>
        <location filename="../audio_text.py" line="31" />
        <source>Cannot play the audio: {detail}</source>
        <translation>Не удалось воспроизвести звук: {detail}</translation>
    </message>
    <message>
        <location filename="../audio_text.py" line="37" />
        <source>Listening failed: {detail}</source>
        <translation>Не удалось вести приём: {detail}</translation>
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
        <location filename="../decode_page.py" line="316" />
        <source>Plain text to select and copy, and the alternative result</source>
        <translation>Простой текст для выделения и копирования, а также альтернативный результат</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="372" />
        <location filename="../decode_page.py" line="682" />
        <source>Open audio file</source>
        <translation>Открыть аудиофайл</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="374" />
        <source>Audio files ({exts})</source>
        <translation>Аудиофайлы ({exts})</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="476" />
        <source>Cannot load audio for playback: {detail}</source>
        <translation>Не удалось загрузить звук для воспроизведения: {detail}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="517" />
        <source>Model result: {text}</source>
        <translation>Результат модели: {text}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="518" />
        <source>DSP fallback result: {text}</source>
        <translation>Резервный результат DSP: {text}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="529" />
        <source>No Morse signal found in this audio.</source>
        <translation>В этом аудио не найден сигнал Морзе.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="531" />
        <source>Tone not detected clearly; guessing from the spectral peak, so the result may be wrong.</source>
        <translation>Тон определён нечётко; берётся пик спектра, поэтому результат может быть неверным.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="534" />
        <source>A second tone was found at {second_hz:.0f} Hz; tracking {tracked_hz:.0f} Hz.</source>
        <translation>Обнаружен второй тон на {second_hz:.0f} Гц; отслеживается {tracked_hz:.0f} Гц.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="536" />
        <source>Low confidence.</source>
        <translation>Низкая уверенность.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="538" />
        <source>Low confidence; the DSP decoder result is shown too.</source>
        <translation>Низкая уверенность; показан также результат DSP-декодера.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="560" />
        <source>File not found: {path}</source>
        <translation>Файл не найден: {path}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="562" />
        <source>Cannot read {path}. Supported formats: {exts}</source>
        <translation>Не удалось прочитать {path}. Поддерживаемые форматы: {exts}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="566" />
        <source>{path} is {minutes} min long; this version supports up to {limit} min.</source>
        <translation>Длительность {path} — {minutes} мин; эта версия поддерживает до {limit} мин.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="568" />
        <source>Setup problem: a model or language model file is missing or unusable.</source>
        <translation>Проблема установки: файл модели или языковой модели отсутствует либо непригоден.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="569" />
        <source>Internal error while decoding. See the log file for details.</source>
        <translation>Внутренняя ошибка при декодировании. Подробности в файле журнала.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="633" />
        <source>Decoding cancelled.</source>
        <translation>Декодирование отменено.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="650" />
        <source>Text files (*.txt)</source>
        <translation>Текстовые файлы (*.txt)</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="650" />
        <source>JSON files (*.json)</source>
        <translation>Файлы JSON (*.json)</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="651" />
        <location filename="../decode_page.py" line="700" />
        <source>Export</source>
        <translation>Экспорт</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="665" />
        <source>Cannot write {path}: {detail}</source>
        <translation>Не удалось записать {path}: {detail}</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="681" />
        <source>Open audio file… (Ctrl+O)</source>
        <translation>Открыть аудиофайл… (Ctrl+O)</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="699" />
        <source>Export to a file: text or JSON with timings</source>
        <translation>Экспорт в файл: текст или JSON с временными метками</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="701" />
        <source>Text file (.txt)…</source>
        <translation>Текстовый файл (.txt)…</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="702" />
        <source>JSON with word timings (.json)…</source>
        <translation>JSON с временем каждого слова (.json)…</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="703" />
        <source>Decoded text</source>
        <translation>Расшифрованный текст</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="711" />
        <source>Open or drop an audio file to see its spectrogram.</source>
        <translation>Откройте или перетащите аудиофайл, чтобы увидеть его спектрограмму.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="683" />
        <source>Message language:</source>
        <translation>Язык сообщения:</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="315" />
        <source>Hide</source>
        <translation>Скрыть</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="315" />
        <source>Show</source>
        <translation>Показать</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="541" />
        <source>Only clicks were heard, no Morse tone. If this is a telegraph key or sounder: MorseDesk decodes Morse sent as a tone (radio CW); key clicks cannot be decoded yet.</source>
        <translation>Слышны только щелчки, тонального сигнала Морзе нет. Если это телеграфный ключ или клопфер: MorseDesk декодирует Морзе, переданную тоном (радио CW); щелчки ключа пока не декодируются.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="685" />
        <source>Auto</source>
        <translation>Авто</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="686" />
        <source>English</source>
        <translation>Английский</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="687" />
        <source>Russian</source>
        <translation>Русский</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="688" />
        <source>Kazakh</source>
        <translation>Казахский</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="692" />
        <source>Use language model</source>
        <translation>Использовать языковую модель</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="693" />
        <source>Auto always uses the language model.</source>
        <translation>Режим «Авто» всегда использует языковую модель.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="695" />
        <source>Decode</source>
        <translation>Декодирование</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="696" />
        <source>Cancel</source>
        <translation>Отмена</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="697" />
        <source>Copy the decoded text</source>
        <translation>Копировать расшифрованный текст</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="698" />
        <source>Copy</source>
        <translation>Копировать</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="704" />
        <source>Plain text</source>
        <translation>Простой текст</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="707" />
        <source>No file selected. Drop an audio file here.</source>
        <translation>Файл не выбран. Перетащите аудиофайл сюда.</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="708" />
        <source>Sample</source>
        <translation>Пример</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="709" />
        <source>Signal</source>
        <translation>Сигнал</translation>
    </message>
    <message>
        <location filename="../decode_page.py" line="710" />
        <source>Open or drop an audio file to see its signal in 3D.</source>
        <translation>Откройте или перетащите аудиофайл, чтобы увидеть его сигнал в 3D.</translation>
    </message>
</context>
<context>
    <name>EncodePage</name>
    <message>
        <location filename="../encode_page.py" line="486" />
        <source>Estimated audio is {minutes} min long; the limit is {limit} min. Shorten the text or raise the speed.</source>
        <translation>Расчётная длительность аудио {minutes} мин, предел {limit} мин. Сократите текст или увеличьте скорость.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="556" />
        <source>Invalid timing settings: the Farnsworth speed must not exceed the speed in WPM.</source>
        <translation>Неверные параметры тайминга: скорость Фарнсворта не должна превышать скорость в WPM.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="559" />
        <source>Could not build the audio.</source>
        <translation>Не удалось построить аудио.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="650" />
        <source>Save audio</source>
        <translation>Сохранить аудио</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="650" />
        <source>Audio ({ext})</source>
        <translation>Аудио ({ext})</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="677" />
        <source>Cannot write {path}: {detail}</source>
        <translation>Не удалось записать {path}: {detail}</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="686" />
        <source>Text to encode</source>
        <translation>Текст для кодирования</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="687" />
        <source>Morse code:</source>
        <translation>Код Морзе:</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="692" />
        <source>Type text to see its Morse code.</source>
        <translation>Введите текст, чтобы увидеть код Морзе.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="319" />
        <location filename="../encode_page.py" line="693" />
        <source>English</source>
        <translation>Английский</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="319" />
        <location filename="../encode_page.py" line="694" />
        <source>Russian</source>
        <translation>Русский</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="319" />
        <location filename="../encode_page.py" line="694" />
        <source>Kazakh</source>
        <translation>Казахский</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="321" />
        <source>Detected alphabet: {name}</source>
        <translation>Определённый алфавит: {name}</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="408" />
        <location filename="../encode_page.py" line="550" />
        <source>Cannot encode {chars} — fix the text or switch alphabet before sending.</source>
        <translation>Невозможно закодировать {chars} — исправьте текст или смените алфавит перед передачей.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="459" />
        <source>Length ≈ {t}</source>
        <translation>Длительность ≈ {t}</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="688" />
        <source>The message appears here as signal-lamp marks.</source>
        <translation>Здесь сообщение появится в виде сигнальных огней.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="689" />
        <source>Alphabet</source>
        <translation>Алфавит</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="689" />
        <source>Timing</source>
        <translation>Тайминг</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="690" />
        <source>Sound</source>
        <translation>Звук</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="690" />
        <source>File</source>
        <translation>Файл</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="693" />
        <source>Auto</source>
        <translation>Авто</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="701" />
        <source>Profile:</source>
        <translation>Профиль:</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="702" />
        <source>Speed (WPM):</source>
        <translation>Скорость (WPM):</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="703" />
        <source>Farnsworth (WPM):</source>
        <translation>Фарнсворт (WPM):</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="704" />
        <source>Weight:</source>
        <translation>Вес:</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="705" />
        <source>Tone (Hz):</source>
        <translation>Тон (Гц):</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="706" />
        <source>Add noise, SNR (dB):</source>
        <translation>Добавить шум, ОСШ (дБ):</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="707" />
        <source>Format:</source>
        <translation>Формат:</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="712" />
        <source>Play</source>
        <translation>Воспроизвести</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="713" />
        <source>Click a letter to play from there.</source>
        <translation>Щёлкните по букве, чтобы воспроизвести с этого места.</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="714" />
        <source>The key presses in time with the sound when you press Play.</source>
        <translation>Ключ нажимается в такт звуку, когда вы нажимаете «Воспроизвести».</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="717" />
        <source>Stop</source>
        <translation>Стоп</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="718" />
        <source>Save…</source>
        <translation>Сохранить…</translation>
    </message>
    <message>
        <location filename="../encode_page.py" line="719" />
        <source>Playing — press Stop to edit the text.</source>
        <translation>Идёт воспроизведение — нажмите «Стоп», чтобы изменить текст.</translation>
    </message>
</context>
<context>
    <name>LivePage</name>
    <message>
        <location filename="../live_page.py" line="253" />
        <source>No input device found. Plug in a sound card or check that PortAudio is installed.</source>
        <translation>Устройство ввода не найдено. Подключите звуковую карту или проверьте установку PortAudio.</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="283" />
        <source>Hz</source>
        <translation>Гц</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="283" />
        <source>dB</source>
        <translation>дБ</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="283" />
        <source>WPM</source>
        <translation>WPM</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="283" />
        <source>s</source>
        <translation>с</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="288" />
        <location filename="../live_page.py" line="419" />
        <source>English</source>
        <translation>Английский</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="288" />
        <location filename="../live_page.py" line="419" />
        <source>Russian</source>
        <translation>Русский</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="288" />
        <location filename="../live_page.py" line="420" />
        <source>Kazakh</source>
        <translation>Казахский</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="297" />
        <source>WPM {v:.1f}</source>
        <translation>Слов/мин {v:.1f}</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="299" />
        <source>Tone {v:.0f} Hz</source>
        <translation>Тон {v:.0f} Гц</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="301" />
        <source>SNR {v:.1f} dB</source>
        <translation>ОСШ {v:.1f} дБ</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="304" />
        <source>Alphabet: {v}</source>
        <translation>Алфавит: {v}</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="305" />
        <source>{v:.0f} s heard</source>
        <translation>принято {v:.0f} с</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="387" />
        <source>Only clicks were heard, no Morse tone. If this is a telegraph key or sounder: MorseDesk decodes Morse sent as a tone (radio CW); key clicks cannot be decoded yet.</source>
        <translation>Слышны только щелчки, тонального сигнала Морзе нет. Если это телеграфный ключ или клопфер: MorseDesk декодирует Морзе, переданную тоном (радио CW); щелчки ключа пока не декодируются.</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="414" />
        <source>Input:</source>
        <translation>Вход:</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="415" />
        <source>Alphabet:</source>
        <translation>Алфавит:</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="417" />
        <source>Auto detects the alphabet from the message itself</source>
        <translation>«Авто» определяет алфавит по самому сообщению</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="418" />
        <source>Refresh</source>
        <translation>Обновить</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="419" />
        <source>Auto</source>
        <translation>Авто</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="423" />
        <source>Look for newly plugged devices</source>
        <translation>Найти недавно подключённые устройства</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="424" />
        <source>Stop</source>
        <translation>Стоп</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="424" />
        <source>Listen</source>
        <translation>Слушать</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="425" />
        <source>Input level</source>
        <translation>Уровень входного сигнала</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="426" />
        <source>Level</source>
        <translation>Уровень</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="427" />
        <source>Alphabet</source>
        <translation>Алфавит</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="428" />
        <source>Tone</source>
        <translation>Тон</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="429" />
        <source>Speed</source>
        <translation>Скорость</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="430" />
        <source>SNR</source>
        <translation>ОСШ</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="431" />
        <source>Heard</source>
        <translation>Принято</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="432" />
        <source>Signal</source>
        <translation>Сигнал</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="433" />
        <source>Press Listen to see the band live in 3D.</source>
        <translation>Нажмите «Слушать», чтобы видеть диапазон в 3D в реальном времени.</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="434" />
        <source>Press Listen to see the band live.</source>
        <translation>Нажмите «Слушать», чтобы видеть диапазон в реальном времени.</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="436" />
        <source>Grey words may still change. Underlined words are uncertain; point at any word for details.</source>
        <translation>Серые слова ещё могут измениться. Подчёркнутые слова сомнительны; наведите на слово, чтобы узнать подробности.</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="440" />
        <source>Copy the decoded text</source>
        <translation>Копировать расшифрованный текст</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="441" />
        <source>Copy</source>
        <translation>Копировать</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="442" />
        <source>Clear the text and start over</source>
        <translation>Очистить текст и начать заново</translation>
    </message>
    <message>
        <location filename="../live_page.py" line="443" />
        <source>Clear</source>
        <translation>Очистить</translation>
    </message>
</context>
<context>
    <name>MainWindow</name>
    <message>
        <location filename="../main_window.py" line="174" />
        <source>MorseDesk</source>
        <translation>MorseDesk</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="175" />
        <source>UI language:</source>
        <translation>Язык интерфейса:</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="180" />
        <source>Decode</source>
        <translation>Декодирование</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="182" />
        <source>Listen</source>
        <translation>Слушать</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="184" />
        <source>Encode</source>
        <translation>Кодирование</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="186" />
        <source>About</source>
        <translation>О программе</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="188" />
        <source>Settings</source>
        <translation>Настройки</translation>
    </message>
    <message>
        <location filename="../main_window.py" line="229" />
        <source>Finishing the current decode; the window will close right after.</source>
        <translation>Завершается текущее декодирование; окно закроется сразу после этого.</translation>
    </message>
</context>
<context>
    <name>PlayerBar</name>
    <message>
        <location filename="../widgets/player_bar.py" line="288" />
        <location filename="../widgets/player_bar.py" line="289" />
        <source>Unmute</source>
        <translation>Включить звук</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="288" />
        <location filename="../widgets/player_bar.py" line="289" />
        <source>Mute</source>
        <translation>Выключить звук</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="290" />
        <source>Volume: {v} %</source>
        <translation>Громкость: {v} %</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="291" />
        <source>Volume</source>
        <translation>Громкость</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="341" />
        <source>Pause</source>
        <translation>Пауза</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="341" />
        <source>Play</source>
        <translation>Воспроизвести</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="344" />
        <source>Pause playback</source>
        <translation>Приостановить воспроизведение</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="344" />
        <source>Listen to the decoded audio</source>
        <translation>Прослушать декодированный сигнал</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="345" />
        <source>Drag to jump to a moment</source>
        <translation>Перетащите, чтобы перейти к моменту</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="346" />
        <source>Playback speed (the pitch stays the same)</source>
        <translation>Скорость воспроизведения (высота тона не меняется)</translation>
    </message>
    <message>
        <location filename="../widgets/player_bar.py" line="347" />
        <source>Playback speed</source>
        <translation>Скорость воспроизведения</translation>
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
        <location filename="../settings_page.py" line="127" />
        <source>version {v}</source>
        <translation>версия {v}</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="129" />
        <source>{n} parameters</source>
        <translation>{n} параметров</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="131" />
        <source>Decoding engine</source>
        <translation>Движок декодирования</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="132" />
        <source>Acoustic model</source>
        <translation>Акустическая модель</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="133" />
        <source>Language models</source>
        <translation>Языковые модели</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="133" />
        <location filename="../settings_page.py" line="136" />
        <source>none found</source>
        <translation>не найдено</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="134" />
        <source>MP3 export</source>
        <translation>Экспорт MP3</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="135" />
        <source>Formats written directly</source>
        <translation>Форматы для прямой записи</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="136" />
        <source>Sound inputs</source>
        <translation>Звуковые входы</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="137" />
        <source>Log file</source>
        <translation>Файл журнала</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="142" />
        <source>Neural network (ONNX) with the classic DSP decoder</source>
        <translation>Нейросеть (ONNX) и классический DSP-декодер</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="143" />
        <source>Classic DSP decoder only</source>
        <translation>Только классический DSP-декодер</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="154" />
        <source>This computer</source>
        <translation>Этот компьютер</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="158" />
        <source>Open log folder</source>
        <translation>Открыть папку журнала</translation>
    </message>
    <message>
        <location filename="../settings_page.py" line="159" />
        <source>Copy report</source>
        <translation>Копировать отчёт</translation>
    </message>
</context>
<context>
    <name>SignalPanel</name>
    <message>
        <location filename="../widgets/signal_panel.py" line="298" />
        <source>{tone} Hz ± 250 Hz</source>
        <translation>{tone} Гц ± 250 Гц</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="329" />
        <source>{db:+.0f} dB above noise</source>
        <translation>{db:+.0f} дБ над шумом</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="332" />
        <source>{t:.1f} s ago</source>
        <translation>{t:.1f} с назад</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="341" />
        <source>Back to live</source>
        <translation>К прямому эфиру</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="342" />
        <source>Follow playback</source>
        <translation>Следовать за звуком</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="345" />
        <source>s</source>
        <translation>с</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="345" />
        <source>Hz</source>
        <translation>Гц</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="346" />
        <source>3D</source>
        <translation>3D</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="347" />
        <source>Spectrogram</source>
        <translation>Спектрограмма</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="348" />
        <source>Show the signal as a 3D landscape</source>
        <translation>Показать сигнал в виде 3D-рельефа</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="349" />
        <source>Show the signal as a spectrogram</source>
        <translation>Показать сигнал в виде спектрограммы</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="350" />
        <source>The view follows the sound again</source>
        <translation>Вид снова следует за звуком</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="351" />
        <source>Drag or scroll to look back; click to replay after you stop</source>
        <translation>Тяните или прокручивайте, чтобы вернуться назад; после остановки щелчок проигрывает запись</translation>
    </message>
    <message>
        <location filename="../widgets/signal_panel.py" line="352" />
        <source>Drag or scroll to move, click to listen from there</source>
        <translation>Тяните или прокручивайте, чтобы перемещаться; щёлкните, чтобы слушать отсюда</translation>
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
        <location filename="../widgets/word_view.py" line="386" />
        <source>high</source>
        <translation>высокая</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="387" />
        <source>No underline: the decoder was sure of every letter in this word.</source>
        <translation>Без подчёркивания: декодер был уверен в каждой букве этого слова.</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="389" />
        <source>medium</source>
        <translation>средняя</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="390" />
        <source>Yellow underline: the decoder was only fairly sure of some letters in this word.</source>
        <translation>Жёлтое подчёркивание: в некоторых буквах этого слова декодер был уверен лишь отчасти.</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="393" />
        <source>low</source>
        <translation>низкая</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="394" />
        <source>Red underline: the decoder was unsure of this word. Check it by ear.</source>
        <translation>Красное подчёркивание: декодер не уверен в этом слове. Проверьте его на слух.</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="396" />
        <source>Confidence {value} ({level})</source>
        <translation>Уверенность {value} ({level})</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="402" />
        <source>In our tests, words at this level were right about {percent} % of the time.</source>
        <translation>В наших измерениях слова с такой уверенностью были верны примерно в {percent} % случаев.</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="406" />
        <source>Grey: not final yet. It may still change as more audio arrives.</source>
        <translation>Серый: ещё не окончательно. Может измениться по мере поступления звука.</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="407" />
        <source>{start}–{end} s</source>
        <translation>{start}–{end} с</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="525" />
        <source>Words appear here as they are heard.</source>
        <translation>Здесь появятся слова по мере приёма.</translation>
    </message>
    <message>
        <location filename="../widgets/word_view.py" line="526" />
        <source>Open an audio file to decode.</source>
        <translation>Откройте аудиофайл для декодирования.</translation>
    </message>
</context>
</TS>