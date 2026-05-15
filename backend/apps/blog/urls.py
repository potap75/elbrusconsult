from django.urls import path

from .views import BlogDetailView, BlogListView, CategoryPostListView, TagPostListView

urlpatterns = [
    path("", BlogListView.as_view(), name="blog-list"),
    path("category/<slug:slug>/", CategoryPostListView.as_view(), name="blog-category"),
    path("tag/<slug:slug>/", TagPostListView.as_view(), name="blog-tag"),
    path("<slug:slug>/", BlogDetailView.as_view(), name="blog-detail"),
]
