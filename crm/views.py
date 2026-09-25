from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse


@staff_member_required(login_url="/admin/login/")
def dashboard(request):
    return HttpResponse("SmartCRM – đang xây dựng")
