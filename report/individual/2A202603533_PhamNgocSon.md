# Báo cáo cá nhân — Day 6: Data Ingestion Engineering

Phạm Ngọc Sơn · 2A202603533 · L3A. Mọi số liệu lấy từ `results/` (xem `results/summary.md`, sinh bởi `starter/scripts/summary.py`). Chạy ngày 2026-11-13, một lần, trên CPU.

## Dữ liệu và pipeline

- **Chủ đề, nguồn/quyền, số trang:** Hệ điều hành — OpenStax *Introduction to Computer Science*, Chương 6 (PDF 939 trang, dùng trang **249–294**). Giấy phép CC BY-NC-SA 4.0 (Rice University), dùng cho bài tập phi thương mại; PDF 56 MB **không commit** (`.gitignore`), URL + SHA-256 trong `data/manifest.json`. Quy tắc đếm: mọi trang vật lý 249–294 (từ trang mở chương tới hết 6.6), loại Chapter Review (295+); một trang chỉ tính khi văn bản chuẩn hóa ≥ 200 ký tự. Kết quả: **46/46 trang hợp lệ**, 136 639 ký tự, 0 trang lỗi/rỗng (`results/errors.log` rỗng). `gold_page` là số trang **PDF vật lý** (khác số in ở chân trang, ví dụ trang PDF 251 in là 241).
- **Chuẩn hóa, lỗi và giới hạn:** `pypdf` theo từng trang → NFC, bỏ chân trang/đầu trang lặp ("Access for free at openstax.org", "6.3 ● … 259"), nối dòng bị ngắt thành đoạn bằng heuristic (dòng ngắn kết thúc `.!?:)` kết thúc đoạn; dòng ngắn không dấu câu là tiêu đề). Hạn chế: bảng, code và hình bị phẳng hóa thành chuỗi (ví dụ Table 6.1 lẫn vào đoạn kế tiếp); chunk **không vượt qua ranh giới trang** nên đoạn văn ngắt trang bị tách.
- **Embedding / store / chi phí:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers 6.3.0, torch 2.15.0 CPU, **384 chiều**, `max_seq_length` 128 token), chuẩn hóa L2, cùng cách mã hóa cho query và document. PostgreSQL 16.16 + pgvector 0.8.7 (Docker), **cosine, tìm kiếm exact (không có index ANN)**, cổng 55433. Chi phí **0 USD** (local). Lệnh chạy: README mục "Bài làm: cách chạy lại". Thời gian: tải model 37,1 s (không tính vào ingest), embed A 12,1 s + ghi 0,3 s; embed B 8,6 s + ghi 0,2 s.
- **Metadata:** bắt buộc `document_id`, `source` (URL), `page`; thêm **`section`** (kiểu chuỗi, 7 giá trị: `intro`, `6.1`…`6.6`), lấy từ **outline (bookmark) của PDF** theo trang bắt đầu mục, không tự đoán. Lý do chọn: câu hỏi thực tế thường nêu rõ mục ("trong phần quản lý bộ nhớ…") và các mục có từ vựng chồng lấn (memory ở 6.2/6.4, security ở 6.2/6.6). Hạn chế đã đo ở phần Metadata bên dưới.

## Cấu hình và benchmark

- **A:** chunk cố định 500 ký tự, overlap 50, không lọc. **B:** chunk theo đoạn/tiêu đề, tối đa 800 ký tự (đoạn dài tách theo câu, tiêu đề ngắn dính vào đoạn sau), không lọc. **C:** dùng đúng chỉ mục của B (cùng chunk, cùng vector), **khác biệt duy nhất B–C: thêm `WHERE section = <filter>`** cho 5/22 câu có `filter`; 17 câu còn lại C chạy không lọc, giống B. A→B đổi chunking (cùng model, corpus, metadata, câu hỏi).
- **22 câu: 16 dev / 6 test**, viết và kiểm chứng trước khi chạy retrieval (`benchmark/questions.jsonl`; script `validate_benchmark.py` kiểm tra mỗi `evidence_quote` nằm nguyên văn trong văn bản chuẩn hóa của `gold_page`, đủ số lượng, không câu test nào dùng chung trang gold với dev, và giá trị filter không loại mất trang gold). **5 câu filter** (dev d04, d09, d12; test t02, t04). Loại câu: trực tiếp / diễn đạt lại / điều kiện / filter. Cách chia và nguy cơ rò rỉ: `benchmark/split-rationale.md`.
- **Tiêu chí chọn chiến lược chốt trước** (`docs/decision-criteria.md`): Hit@3 dev → Hit@1 dev → grounding/coherence → tài nguyên; test chỉ để báo cáo. Tham số 500/50 và 800 chốt trước và **không chỉnh sau khi xem kết quả**.

## Kết quả

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian ingest | Chi phí |
|---|---|---|---|---|---|---|
| A | dev | 5/16 | 8/16 | 319 | 12,4 s | 0 |
| A | test | 4/6 | 4/6 | 319 | (cùng lần) | 0 |
| B | dev | 10/16 | 14/16 | 242 | 8,8 s | 0 |
| B | test | 2/6 | 5/6 | 242 | (cùng lần) | 0 |
| C | dev | 10/16 | 14/16 | 242 (dùng lại B) | 0 thêm | 0 |
| C | test | 3/6 | 5/6 | 242 (dùng lại B) | 0 thêm | 0 |

Tổng 22 câu: A 9/22 và 12/22; B 12/22 và 19/22; C 13/22 và 19/22 (Hit@1 và Hit@3).

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N hoặc N/A) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| A | 0,80 (10) | 13/15 | N/A — không áp filter (top-3 tình cờ đúng mục: 3/5 câu filter) | 1/1/3 → 1,40 |
| B | 1,90 (10) | 13/15 | N/A — không áp filter (tình cờ 3/5) | 0/0/5 → 2,00 |
| C | 1,90 (10) | 14/15 | **5/5** câu filter (test 2/2) | 0/0/5 → 2,00 |

Chunk: A 319 chunk (74/500/500/500 ký tự min/median/p95/max, ≈33 961 token), B 242 chunk (25/612,5/784/800, ≈30 612 token). Nạp lại cùng phiên bản: A 319→319, B 242→242, 0 bản ghi trùng. Tài liệu đổi (thêm một đoạn vào 1 trang, thử trên strategy tạm `TMP`): 1 chunk cũ bị xóa, số dòng = số chunk mới (33), 0 chunk cũ còn sót (`results/reingest_changed_doc.json`).

**Trace, nhãn, cách chọn mẫu:** `results/traces_{A,B,C}.jsonl` (top-3 đầy đủ: id, text, score, metadata, hit), `results/metrics.json`, `results/analysis.json`, `results/audit/{coherence,metadata,grounding}.csv`. Mẫu chốt theo quy tắc, không theo điểm: coherence = 10 page ID nhỏ nhất (249–258), vị trí = ký tự giữa trang, chấm chunk phủ vị trí đó; metadata và grounding = t01–t05 × top-3 (t06 là câu test thứ sáu, không vào mẫu audit).

**Cách chấm — cần đọc kỹ:** nhãn coherence và grounding được gán bằng cách đọc văn bản chunk, **do Claude (AI) thực hiện và chưa được tác giả kiểm lại**; chúng độc lập với Hit@k nhưng không phải nhãn của nhiều người chấm. Kiểm tra metadata là kiểm tra tự động bằng mã (chunk có nằm trong trang được ghi không; `section` có đúng với vị trí thật của chunk trong trang không), kèm lý do từng lỗi.

## Phân tích và kết luận

**A→B (đổi chunking).** Dev tăng rõ: Hit@1 5→10/16, Hit@3 8→14/16; 6 câu dev (d03, d06, d09, d11, d13, d14) chuyển từ trượt sang trúng Hit@3 (không câu dev nào chiều ngược lại) nhờ chunk giữ nguyên câu chứa bằng chứng. Coherence 0,80→1,90 và grounding 1,40→2,00 cùng hướng. Nhưng trên **test** Hit@1 lại giảm 4/6→2/6 (Hit@3 tăng 4/6→5/6): ở t05, t02 chunk đúng vẫn nằm trong top-3 nhưng không còn ở hạng 1. Test chỉ 6 câu (một câu = 16,7 điểm %), nên không đủ để nói A hay B tốt hơn trên test. Chi phí: B ít chunk hơn 24% (242 vs 319) và nhanh hơn (8,8 s vs 12,4 s, một lần đo trên CPU).

**B→C (thêm filter `section`).** Dev **không đổi** (Hit@1 10/16, Hit@3 14/16). Test Hit@1 2/6→3/6 do một câu (t02: chunk đúng lên hạng 1). Ở dev, filter chỉ đổi thứ hạng của chunk sai (d09: chunk lạc mục 6.3 được thay bằng chunk của 6.4). Filter tuân thủ 5/5 vì lọc bằng SQL, và phải đọc là **bắt buộc đúng theo thiết kế**, không phải kết quả đo thông minh. C tốn 0 chi phí ingest thêm. Giới hạn: 5/22 câu có filter; chênh lệch 1 câu không có ý nghĩa thống kê.

**Hai ví dụ sai.**
1. **d15** (dev, `Extensibility Can new features be added?`, trang 252, mục 6.1) — trượt ở cả A, B, C: top-3 là chunk về "Layered OS Design" (trang 263–264). Dòng chứa bằng chứng là một hàng của Table 6.1 bị phẳng hóa; trong B hàng này nằm ở ký tự ~315/657 của một chunk gồm ~10 hàng khác của bảng (chunk gần như hoàn toàn là danh sách câu hỏi thiết kế), nên vector là chủ đề chung "OS design questions" và không đủ đặc hiệu cho một hàng. Đây là giả thuyết hợp lý từ nội dung chunk, tôi chưa kiểm chứng bằng thí nghiệm riêng. Nguyên nhân gốc có thể là bảng bị phẳng hóa khi trích PDF.
2. **t06** (test, "What mechanism lets separate running programs exchange data and collaborate?", trang 270) — A: có 2 chunk trang 270 trong top-3 nhưng không chunk nào chứa câu định nghĩa IPC (đoạn đó nằm ở chunk khác không được truy xuất); B/C: chunk đúng ("Inter-Process Communication", trang 270) không vào top-3, thay bằng chunk về "sharing" (trang 278) và "shared resources" (trang 276). Câu hỏi diễn đạt lại bằng "separate running programs / exchange data" thay cho "processes / IPC", và model nhỏ ưu tiên chủ đề "sharing". Đây là lỗi kiểu ngữ nghĩa lệch, không do chunking hay metadata.

**Một yếu tố gây nhiễu phát hiện sau khi chạy.** Model có `max_seq_length` = 128 token, nhưng **135/242 chunk B** (và 20/319 chunk A) dài hơn mức đó (`results/analysis.json`), nên vector của chunk dài chỉ phản ánh phần đầu, phần sau vẫn được lưu và vẫn được chấm hit nếu truy xuất được. Điều này có thể làm B lẽ ra tốt hơn nếu chunk ≤ 128 token, và làm A–B bị lẫn giữa "kích thước chunk" với "cấu trúc đoạn". Tôi không đổi B sau khi xem kết quả (tránh tinh chỉnh theo test); đây là cải tiến ưu tiên khi làm lại.

**Metadata (hữu ích và hạn chế).** `page` giúp truy vết tức thời (mọi top-3 đều chứa văn bản có thật trên trang được ghi: 0/45 lỗi `page`, `source`, `document_id`). `section` giúp lọc đúng phạm vi (5/5 trong C). Hạn chế đo được: 5/45 bản ghi sai ở `section` — 3 ở A/B/C trang 277 (tiêu đề 6.4 nằm giữa trang nên phần đầu trang vẫn thuộc 6.3) và 2 ở trang 284 (6.5 bắt đầu giữa trang). Nên `section` theo trang gán nhầm mục cho nửa trang; với filter, một câu có bằng chứng ở nửa trang đầu của trang chuyển mục sẽ bị loại nhầm. Trong benchmark này, `validate_benchmark.py` đảm bảo không câu filter nào dính lỗi đó; đây chưa phải bằng chứng cho corpus khác.

**Chiến lược chọn.** Theo tiêu chí đã chốt, B và C **hòa** ở dev (cùng Hit@3, cùng Hit@1), cũng hòa ở coherence/grounding/tài nguyên, nên các tiêu chí không phân thắng bại giữa hai bên; A thua rõ ở dev. Khuyến nghị thực tế: dùng **B khi không có phạm vi mục đáng tin; dùng C khi người dùng/ngữ cảnh cung cấp sẵn `section`** (không tốn thêm chi phí, đảm bảo trả về đúng phạm vi). Điều kiện áp dụng: `section` phải chính xác tới từng đoạn, không chỉ từng trang.

**Hạn chế.** (1) Corpus một chương, một ngôn ngữ, một nguồn, nên không suy rộng. (2) Test 6 câu (filter chỉ 2 câu) và dev 16 câu: sai số rất lớn. (3) Tác giả vừa viết câu hỏi, kiểm chứng evidence vừa nhận nhãn; nhãn coherence/grounding do AI gán (xem trên). (4) Thời gian chỉ đo một lần trên CPU, không lặp, chênh 12,4 s vs 8,8 s có thể do nhiễu. (5) Đo grounding chỉ là bằng chứng truy xuất, **không phải độ chính xác câu trả lời LLM**. (6) Tôi xem kết quả test trước khi viết mẫu audit; không sửa tham số hay câu hỏi sau đó, nhưng test không còn là kiểm tra mù đối với phần phân tích này.

**Nếu làm lại hoặc mở rộng.** (a) Chọn B tối đa ~450 ký tự hoặc dùng model có `max_seq_length` ≥ 512 để loại nhiễu cắt cụt, rồi đo lại A–B. (b) Gán `section` theo vị trí tiêu đề trong trang thay vì theo trang. (c) Giữ bảng ở dạng hàng riêng khi trích PDF. (d) Mở rộng lên 60+ câu có 15+ câu test, lặp đo thời gian, và để người khác chấm nhãn. (e) Thử hybrid BM25 + dense (mục tùy chọn) cho các câu diễn đạt lại như t06.

**Công cụ AI và cách kiểm tra (RULES.md).** Mã nguồn, câu hỏi benchmark và nhãn audit được viết có sự hỗ trợ của Claude (Claude Code). Cách kiểm tra: mọi `evidence_quote` được kiểm bằng script với văn bản chuẩn hóa; Hit@k tính bằng mã từ trace thật; 6 unit test cho chunking (`starter/tests`); các số trong báo cáo được sinh từ `results/summary.md`. Chưa được kiểm tra bởi người thứ hai.

**Độ lệch so với starter.** Bỏ bind-mount `init.sql` khỏi `docker-compose.yml` vì Docker Desktop trên máy báo `invalid volume specification`; thay bằng `CREATE EXTENSION IF NOT EXISTS vector` trong `create_schema()`.
