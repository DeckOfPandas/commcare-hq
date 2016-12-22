from django.conf.urls import url

from corehq.apps.toggle_ui.views import ToggleListView, ToggleEditView

urlpatterns = [
    url(r'^$', ToggleListView.as_view(), name=ToggleListView.urlname),
    url(r'^edit/(?P<toggle>[\w_-]+)/$', ToggleEditView.as_view(), name=ToggleEditView.urlname),
]
