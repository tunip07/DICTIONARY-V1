# Adam Dictionary / 
DỰ ÁN NHỎ BỊ ĐẤM CHẾT BỚI SONNT PFP191 FPTU

Repo này gồm **2 ứng dụng**:

1. **Web app React + Vite** ở thư mục gốc `We/`
2. **Desktop app Python + CustomTkinter** ở `We/LingoQuest/`

Phần từ điển chính, notebook, game webcam, YouTube, News và toàn bộ data runtime hiện nằm ở:

- `C:\Users\Adam\Downloads\We\LingoQuest`

README này được viết lại để chuẩn bị public lên GitHub, nên tập trung vào:

- chức năng của từng file/folder quan trọng
- cách chạy từng app
- nguyên lý **thêm từ**
- nguyên lý **xóa từ**
- nguyên lý **đồng bộ IPA / pronunciation / phonetic**
- kiến trúc **search engine** và **độ phức tạp**

---

## 1. Tổng quan tính năng

### Web app

- giao diện React/Vite
- intro screen và hero UI
- AI/generative flow cho phần web
- gọi backend API nội bộ để lấy từ điển, video, news

### Desktop app

- tra từ tiếng Anh -> nghĩa tiếng Việt
- notebook từ vựng cục bộ bằng `genz_dict.json`
- thêm từ / xóa từ / import / export
- autocomplete + fuzzy search
- Word of the Day
- Daily Challenge / quiz / flashcard
- YouTube videos liên quan đến từ
- News liên quan đến từ
- mini-game webcam `Dodge Arena`

---

## 2. Cấu trúc thư mục

```text
We/
|- App.tsx
|- index.tsx
|- index.html
|- index.css
|- package.json
|- vite.config.ts
|- components/
|- services/
`- LingoQuest/
   |- main.py
   |- app.py
   |- ui.py
   |- intro.py
   |- home_dashboard_ui.py
   |- engine.py
   |- api.py
   |- storage.py
   |- crud.py
   |- quiz.py
   |- backend.py
   |- youtube_panel.py
   |- news_panel.py
   |- game_dodge.py
   |- genz_dict.json
   |- app_state.json
   |- config.example.json
   `- assets/
```

---

## 3. Cách chạy

## 3.1. Desktop app

```powershell
cd C:\Users\Adam\Downloads\We\LingoQuest
python .\main.py
```

## 3.2. Game webcam chạy riêng

```powershell
cd C:\Users\Adam\Downloads\We\LingoQuest
python .\game_dodge.py
```

## 3.3. Backend API cho web app

```powershell
cd C:\Users\Adam\Downloads\We\LingoQuest
python .\backend.py
```

## 3.4. Web app React

```powershell
cd C:\Users\Adam\Downloads\We
npm install
npm run dev
```

---

## 4. Chức năng của từng file quan trọng

## 4.1. Root web app

- `App.tsx`
  - container chính của web app
  - quản lý intro, topic input, search, AI state, loading state
  - có gọi backend nội bộ để lấy dictionary/news/youtube

- `index.tsx`
  - bootstrap React

- `index.html`
  - shell HTML của Vite

- `index.css`
  - CSS global

- `components/`
  - các component UI của web app

- `services/`
  - service layer cho web app
  - ví dụ gọi Gemini / dictionary service

- `package.json`
  - scripts và dependencies của frontend

---

## 4.2. Desktop app `LingoQuest/`

### Điều phối / UI

- `main.py`
  - entrypoint của app desktop

- `app.py`
  - file điều phối chính
  - nối toàn bộ screen, action, callback và luồng runtime
  - đây là file lớn nhất và là trung tâm của app desktop

- `ui.py`
  - helper style, font, gradient, colors

- `intro.py`
  - intro animation / intro overlay

- `home_dashboard_ui.py`
  - block UI cho home dashboard:
    - search shell
    - cards
    - daily challenge
    - recent searches

### Dữ liệu / CRUD / import-export

- `storage.py`
  - schema dữ liệu từ điển
  - normalize entry
  - repair text lỗi encoding
  - load/save JSON
  - import legacy TXT
  - export CSV/TSV/TXT rút gọn

- `crud.py`
  - thêm/cập nhật/xóa từ
  - import nhiều dòng
  - toggle favorite
  - update field đơn lẻ

- `genz_dict.json`
  - file dữ liệu chính của kho từ vựng

- `app_state.json`
  - state runtime nhẹ
  - ví dụ recent searches, daily state

### Search / API / quiz

- `engine.py`
  - search engine cục bộ
  - exact lookup, autocomplete, meaning search, fuzzy fallback

- `api.py`
  - remote lookup layer
  - DictionaryAPI + Datamuse + translation fallback
  - chọn nghĩa tốt nhất thay vì lấy bừa nghĩa đầu tiên

- `quiz.py`
  - tạo câu hỏi multiple-choice / flashcard / challenge

### Media / game / backend

- `youtube_panel.py`
  - panel video YouTube liên quan đến từ

- `news_panel.py`
  - panel tin tức liên quan từ Google News / publisher

- `game_dodge.py`
  - mini-game webcam `Dodge Arena`

- `backend.py`
  - FastAPI server cho web app
  - expose:
    - `/api/search`
    - `/api/autocomplete`
    - `/api/word-of-day`
    - `/api/add`
    - `/api/youtube`
    - `/api/news`

---

## 5. Nguyên lý thêm từ

App có 3 đường thêm từ chính:

1. thêm tay từ giao diện
2. import nhiều dòng
3. tra online rồi cache vào kho

### 5.1. Thêm tay / cập nhật tay

Hàm lõi:

- `crud.py -> upsert_word_entry(words, word, incoming, pragmatics="")`

Các bước:

1. chuẩn hóa `word` bằng `normalize_text()`
2. nếu chưa tồn tại thì gắn `added_at`
3. trộn dữ liệu cũ + dữ liệu mới qua `merge_entry()`
4. `merge_entry()` lại gọi `normalize_entry()`
5. ghi vào `words[normalized_word]`

Kết quả:

- từ chưa có -> insert mới
- từ đã có -> update tại chỗ

### 5.2. Import nhiều dòng

Luồng:

- `parse_import_lines()`
- `import_parsed_entries()`
- cuối cùng vẫn đi vào `upsert_word_entry()`

Nghĩa là import không đi đường tắt. Mọi entry vẫn phải qua normalize và merge giống như thêm tay.

### 5.3. Tra online rồi cache

Luồng:

- `api.py -> lookup_remote_word()`
- `api.py -> fetch_and_cache_word()`
- `api.py -> cache_lookup_result()`

Các bước:

1. thử gọi DictionaryAPI
2. nếu fail thì dùng Datamuse suggestion
3. nếu vẫn fail thì dùng translation fallback
4. khi có kết quả, merge vào kho cục bộ
5. ghi lại vào `genz_dict.json`

Ý nghĩa:

- lần đầu tra từ lạ thì có thể chậm hơn
- từ đã cache sẽ tra local nhanh ở lần sau

---

## 6. Nguyên lý xóa từ

### 6.1. Xóa một từ

Hàm lõi:

- `crud.py -> delete_word_entry(words, word)`

Nó làm đúng 2 việc:

1. kiểm tra từ có tồn tại không
2. nếu có thì `del words[word]`

### 6.2. Xóa nhiều từ

Hàm:

- `crud.py -> delete_word_entries(words, selected_words)`

Cách làm:

1. duyệt danh sách chọn
2. gọi `delete_word_entry()` cho từng phần tử
3. đếm số lượng thành công

### 6.3. Điều quan trọng

Xóa trong bộ nhớ **chưa đủ**.

Sau khi xóa, app còn phải:

1. save lại xuống `genz_dict.json`
2. refresh UI / search result / notebook

Nếu không save thì khi mở lại app, từ có thể xuất hiện trở lại.

---

## 7. Nguyên lý IPA / pronunciation / phonetic

App hiện dùng 4 field liên quan phát âm:

- `phonetic`
- `pronunciation`
- `ipa_uk`
- `ipa_us`

Mục tiêu là:

- chấp nhận dữ liệu từ nhiều nguồn
- nhưng khi render thì không bị trống

### 7.1. Lúc fetch từ API

Trong `api.py -> parse_dictionaryapi_payload()`:

- app lấy `entry["phonetic"]`
- nếu không có thì lấy `phonetics[].text` đầu tiên không rỗng

Sau đó cùng một chuỗi này được đổ vào:

- `phonetic`
- `pronunciation`
- `ipa_uk`
- `ipa_us`

Lý do:

- API miễn phí thường không tách UK/US rõ ràng cho mọi từ
- app cần có ít nhất một chuỗi IPA để không trống UI

### 7.2. Đồng bộ trong `storage.py`

Hàm quan trọng:

- `normalize_entry()`

Luồng đồng bộ:

1. làm sạch text bằng `repair_text(...).strip()`
2. nếu `phonetic` trống nhưng `pronunciation` có:
   - copy `pronunciation -> phonetic`
3. nếu `pronunciation` trống nhưng `phonetic` có:
   - copy `phonetic -> pronunciation`
4. nếu `ipa_uk` trống:
   - lấy `phonetic`
5. nếu `ipa_us` trống:
   - lấy `phonetic`

Tóm gọn:

- `phonetic` là field trung tâm
- `pronunciation` là alias UI-friendly
- `ipa_uk` và `ipa_us` là nhánh mở rộng

### 7.3. Thứ tự fallback khi hiển thị

Nhiều màn hình sẽ ưu tiên kiểu:

1. `pronunciation`
2. `phonetic`
3. `ipa_uk`
4. `ipa_us`

Nhờ vậy, dù dữ liệu ban đầu không đủ chuẩn, UI vẫn hiển thị được phát âm.

---

## 8. Search engine hoạt động như thế nào

Search của desktop app là 2 tầng:

1. **local search** trong kho cục bộ bằng `engine.py`
2. **remote lookup** bằng `api.py` nếu local không đủ

### 8.1. Local search

`engine.py` build các index sau:

- `_words`
  - map word -> entry
- `_sorted_words`
  - danh sách từ đã sort
- `_prefix_index`
  - prefix -> list từ
- `_meaning_token_index`
  - token trong meaning -> list từ
- `_meaning_prefix_index`
  - prefix của token meaning -> list từ

Luồng `search(query)`:

1. exact lookup
2. autocomplete/prefix
3. meaning search
4. fuzzy fallback

### 8.2. Remote lookup

Nếu local search không thấy:

1. gọi DictionaryAPI
2. nếu fail thì dùng Datamuse để sửa chính tả/gợi ý
3. nếu vẫn fail thì dùng translation fallback
4. kết quả cuối cùng được cache ngược vào `genz_dict.json`

---

## 9. Search engine complexity

Ký hiệu:

- `n` = số từ trong kho
- `m` = độ dài query
- `k` = số kết quả trả về
- `L` = tổng độ dài tất cả từ / token khi build index

### 9.1. Build index trong `engine.py`

Khi gọi `SearchEngine.set_words(words)`:

- normalize toàn bộ key: xấp xỉ `O(n)`
- sort từ: `O(n log n)`
- build `_prefix_index` cho từng prefix của từng từ: xấp xỉ `O(L)`
- build index cho token meaning: xấp xỉ `O(L)`

Vì prefix của mỗi từ đều được ghi sẵn, chi phí build cao hơn search, đổi lại autocomplete rất nhanh.

### 9.2. Exact lookup

`exact_lookup(query)`

- trung bình: `O(1)`

Vì dữ liệu nằm trong dictionary/hash map.

### 9.3. Autocomplete / prefix

`autocomplete(prefix)`

- lookup prefix trong `_prefix_index`: gần `O(1)`
- lấy `k` phần tử đầu: `O(k)`

Tức là:

- thực tế gần `O(k)`

### 9.4. Meaning search

`meaning_contains(query)`

- tokenize query: `O(m)`
- tra từng token trong index: gần `O(1)` mỗi token
- intersect các danh sách kết quả: phụ thuộc số candidate

Thực tế:

- tốt hơn quét toàn bộ `n` từ
- nhưng giao của nhiều danh sách có thể tốn hơn exact lookup

### 9.5. Fuzzy fallback

`fuzzy_suggestions(query)`

- hiện dùng `difflib.get_close_matches`
- phải so với toàn bộ `_sorted_words`

Nên đây là bước nặng nhất của local search:

- xấp xỉ `O(n * m)` hoặc hơn tùy similarity internals

Vì vậy fuzzy chỉ nên chạy khi:

- exact
- prefix
- meaning

đều không ra kết quả.

---

## 10. Chọn nghĩa tốt nhất trong `api.py`

App đã không còn lấy “nghĩa đầu tiên” một cách mù quáng.

Các hàm:

- `_score_dictionaryapi_sense(...)`
- `_select_best_dictionaryapi_sense(entry)`

Nguyên lý chấm điểm:

- ưu tiên nghĩa có `example`
- ưu tiên nghĩa ngắn, dễ học, phổ thông
- ưu tiên `verb` với nhóm headword rất thông dụng như:
  - `have`
  - `do`
  - `make`
  - `get`
  - `go`
  - `take`
- giảm điểm nếu nghĩa có dấu hiệu niche:
  - archaic
  - rare
  - obsolete
  - slang

Nhờ vậy các từ thông dụng như `have` không còn dễ bị chọn nhầm sang nghĩa noun hiếm.

---

## 11. Cấu hình local quan trọng

### YouTube API

Tạo file:

- `LingoQuest/config.json`

Nội dung:

```json
{
  "youtube_api_key": "YOUR_KEY_HERE"
}
```

Repo có sẵn:

- `LingoQuest/config.example.json`

`config.json` hiện được ignore để tránh lộ key.

### Dữ liệu app

- `LingoQuest/genz_dict.json` là dữ liệu chính
- `LingoQuest/app_state.json` là state runtime local

---

## 12. Muốn sửa tính năng nào thì vào file nào

### Muốn sửa UI desktop

- `LingoQuest/app.py`
- `LingoQuest/ui.py`
- `LingoQuest/home_dashboard_ui.py`
- `LingoQuest/intro.py`

### Muốn sửa search cục bộ

- `LingoQuest/engine.py`

### Muốn sửa fetch online / suggestion / collocation / translate fallback

- `LingoQuest/api.py`

### Muốn sửa dữ liệu / schema / export

- `LingoQuest/storage.py`
- `LingoQuest/crud.py`

### Muốn sửa game webcam

- `LingoQuest/game_dodge.py`

### Muốn sửa panel YouTube / News

- `LingoQuest/youtube_panel.py`
- `LingoQuest/news_panel.py`

### Muốn sửa backend cho web app

- `LingoQuest/backend.py`

---

## 13. Kiểm tra nhanh trước khi push GitHub

### Python desktop app

```powershell
cd C:\Users\Adam\Downloads\We\LingoQuest
python -m py_compile app.py api.py storage.py crud.py engine.py game_dodge.py main.py
python -m unittest test_engine.py test_storage.py test_api.py test_crud.py test_quiz.py test_utils.py
```

### Web app

```powershell
cd C:\Users\Adam\Downloads\We
npm run build
```

---

## 14. Ghi chú cuối

Nếu chỉ cần nhớ 4 file quan trọng nhất của desktop app, hãy đọc theo thứ tự:

1. `app.py`
2. `storage.py`
3. `crud.py`
4. `api.py`

Sau đó mới đọc:

5. `engine.py`
6. `quiz.py`
7. `game_dodge.py`

Chỉ cần nắm các file đó là đã hiểu gần như toàn bộ luồng chính của từ điển.
