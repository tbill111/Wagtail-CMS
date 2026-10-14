"""Từ điển cảm xúc tiếng Việt cho nhận xét sản phẩm / dịch vụ (phương pháp "keyword").

Cụm dài được so khớp trước cụm ngắn ("nhanh hết pin" trước "nhanh"). Có cả cách viết tắt hay gặp trên mạng.
"""

POSITIVE = {
    "tốt", "rất tốt", "khá tốt", "ổn", "ổn áp", "ổn định", "ok", "oke", "okela", "oki", "ngon", "ngon lành", "mượt",
    "mượt mà", "đẹp", "tuyệt", "tuyệt vời", "xuất sắc", "hoàn hảo", "hài lòng", "rất hài lòng", "thích", "ưng",
    "ưng ý", "vừa ý", "mãn nguyện", "đáng tiền", "đáng mua", "nên mua", "chất lượng", "nhanh", "trâu", "pin trâu",
    "bền", "sắc nét", "rõ nét", "nét", "nhạy", "êm", "hợp lý", "giá tốt", "giá rẻ", "rẻ", "nhiệt tình", "chu đáo",
    "tận tình", "thân thiện", "chuyên nghiệp", "cảm ơn", "cám ơn", "xịn", "xịn xò", "sang", "sang trọng", "mạnh",
    "mạnh mẽ", "khỏe", "khoẻ", "mát", "ấn tượng", "yêu", "tuyệt cú mèo", "đỉnh", "best", "good", "nice", "great",
    "like", "recommend", "10 điểm", "5 sao", "không có gì để chê", "đáng đồng tiền",
}

NEGATIVE = {
    "tệ", "tệ hại", "kém", "chán", "dở", "lag", "giật", "giật lag", "lỗi", "hỏng", "hư", "nóng", "nóng máy",
    "hao pin", "tụt pin", "nhanh hết pin", "pin yếu", "chậm", "đơ", "treo", "sập nguồn", "thất vọng",
    "phí tiền", "tiếc tiền", "đừng mua", "không nên mua", "lừa", "lừa đảo", "mờ", "nhòe", "nhoè", "yếu", "rè", "ồn",
    "đắt", "mắc", "xấu", "tồi", "tồi tệ", "bực", "bực mình", "khó chịu", "phiền", "lởm", "cùi", "rác", "trầy",
    "xước", "vỡ", "nứt", "chập chờn", "mất sóng", "sóng yếu", "tuột", "hao", "nhanh hết", "tốn pin", "nóng ran",
    "không ổn", "chán nản", "kém chất lượng", "quá tệ", "bad", "tệ quá", "hơi tệ", "không đáng", "lỗi vặt",
    "văng", "thoát app", "chê", "bất tiện", "khó dùng",
}

NEGATIONS = {"không", "ko", "k", "khong", "hông", "chẳng", "chả", "chưa", "đâu có", "đếch", "chưa từng"}

# Cụm dài nhất (tính theo số từ) để so khớp tham lam
MAX_PHRASE = max(len(phrase.split()) for phrase in POSITIVE | NEGATIVE | NEGATIONS)
