from django.urls import path

from . import views

urlpatterns = [
    path('struct-tree/', views.get_struct_tree),
    path('channel-data/', views.get_channel_data),
    path('error-data/', views.get_error_data),
    path('submit-data/', views.submit_data),
    path('operator-strs/', views.process_channel_names),
    path('get-shot-number-index/', views.get_shot_number_index, name='get_shot_number_index'),
    path('get-channel-type-index/', views.get_channel_type_index, name='get-channel-type-index'),
    path('get-channel-name-index/', views.get_channel_name_index, name='get-channel-name-index'),
    path('get-errors-name-index/', views.get_errors_name_index, name='get-errors-name-index'),
    path('get-error-origin-index/', views.get_error_origin_index, name='get-error-origin-index'),

    path('upload/', views.upload_file, name='upload_file'),
    # path('function-details/<str:function_name>/', views.function_details, name='function_details'),
    path('view-functions/', views.view_imported_functions, name='view_imported_functions'),
    path('execute/', views.execute_function, name='execute_function'),
]