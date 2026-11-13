# Cách chia dev/test và nguy cơ rò rỉ

- 22 câu: **16 dev / 6 test**, viết và kiểm chứng evidence (script `starter/scripts/validate_benchmark.py`) trước khi chạy retrieval.
- Chia theo **trang nguồn**: không câu test nào dùng chung `gold_page` với câu dev (script kiểm tra). Test phủ các trang 257, 261, 270, 273, 283, 291 (mục 6.2, 6.3, 6.4, 6.6).
- Loại câu: trực tiếp, diễn đạt lại, điều kiện (nhãn `type`), và `filter`. 5 câu filter (3 dev: d04, d09, d12; 2 test: t02, t04); giá trị filter `section` là input giả định do người dùng cung cấp trước truy xuất, đúng với trang gold (script kiểm tra filter không loại trang gold).
- Câu không filter: cấu hình C chạy không lọc (giống B).
- Nguy cơ rò rỉ: các trang liền kề (vd. 270-271, 273-275) cùng chủ đề tiến trình, một chunk dev có thể chứa ngữ cảnh gần giống câu test; test chỉ 6 câu, mục 6.1 và 6.5 không có câu test.
- Người viết câu hỏi, người kiểm chứng và người chấm đều là tác giả (nguy cơ thiên lệch).
