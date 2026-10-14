from wagtail.admin.forms import WagtailAdminModelForm


class OrderAdminForm(WagtailAdminModelForm):
    """Chặn chuyển đơn sang Hoàn thành khi kho không đủ hàng (báo lỗi ngay trên form)."""

    def is_valid(self):
        # Kiểm tra sau cùng vì dữ liệu các dòng sản phẩm (formset) chỉ có sau khi formset hợp lệ
        if not super().is_valid():
            return False
        items = []
        for form in self.formsets["items"].forms:
            data = getattr(form, "cleaned_data", None)
            if data and not data.get("DELETE"):
                items.append((data.get("product"), data.get("quantity")))
        order = self.instance
        order.status = self.cleaned_data.get("status", order.status)
        shortages = order.stock_shortages(order.stock_delta(order.desired_stock(items)))
        if shortages:
            self.add_error("status", "Không đủ hàng trong kho: " + "; ".join(shortages))
            return False
        return True
