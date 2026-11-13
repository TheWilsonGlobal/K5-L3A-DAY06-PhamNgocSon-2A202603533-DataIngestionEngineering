# Tiêu chí chọn chiến lược (chốt trước khi chạy bất kỳ truy xuất nào)

Ngày chốt: 2026-11-13, trước lần chạy retrieval đầu tiên. `benchmark/questions.jsonl` đã qua `validate_benchmark.py` và không được sửa sau mốc này.

Thứ tự ưu tiên khi so sánh A, B, C (**chỉ tính trên 16 câu dev**):

1. Evidence Hit@3 trên dev cao hơn.
2. Hòa -> Hit@1 trên dev cao hơn.
3. Hòa -> điểm grounding trung bình thủ công (5 câu test, chấm sau) cao hơn, rồi coherence trung bình.
4. Hòa -> ít chunk hơn / thời gian ingest thấp hơn (tài nguyên).

Quy ước:
- Test (6 câu) chỉ để báo cáo; không dùng để chọn tham số hay chiến lược.
- C chỉ được xem là "tốt hơn B" nếu Hit@3 dev của C > B, hoặc bằng nhau mà Hit@1 dev của C > B; C không bị phạt khi chỉ 5/22 câu có filter.
- Tham số (A: 500/50, B: 800) là giá trị chốt trước, không điều chỉnh sau khi xem kết quả. Nếu có chỉnh, phải ghi vào `artifacts/experiment_log.csv` và nêu rõ trong báo cáo.
- Tập test quá nhỏ (6 câu: 1 câu = 16,7 điểm %) nên không rút ra kết luận tổng quát.
