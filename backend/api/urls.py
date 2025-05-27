from django.urls import path

from . import views

urlpatterns = [
    path('struct-tree', views.get_struct_tree),

    path('channel-data', views.get_channel_data),
    path('error-data', views.get_error_data),
    path('get-channels-errors', views.get_channels_errors, name='get_channels_errors'),

    path('operator-strs', views.operator_strs),
    path('operator-strs/init', views.init_calculation, name='init_calculation'),
    path('calculation-progress/<str:task_id>', views.get_calculation_progress, name='get_calculation_progress'),
    path('get-shot-number-index', views.get_shot_number_index, name='get_shot_number_index'),
    path('get-channel-type-index', views.get_channel_type_index, name='get-channel-type-index'),
    path('get-channel-name-index', views.get_channel_name_index, name='get-channel-name-index'),
    path('get-errors-name-index', views.get_errors_name_index, name='get-errors-name-index'),
    path('get-error-origin-index', views.get_error_origin_index, name='get-error-origin-index'),

    path('sketch-query', views.sketch_query, name='sketch_query'),

    path('upload', views.upload_file, name='upload_file'),

    path('view-functions', views.view_imported_functions, name='view_imported_functions'),
    path('execute', views.execute_function, name='execute_function'),
    path('verify-user', views.verify_user, name='verify_user'),
    path('sync-error-data', views.sync_error_data, name='sync_error_data'),
    path('delete-error-data', views.delete_error_data, name='delete_error_data'),
    path('get-ddp-dbs', views.get_datadiagnosticplatform_dbs, name='get_ddp_dbs'),
    path('initialize-db-indices', views.initialize_db_indices, name='initialize_db_indices'),
    path('get-function-params', views.get_function_params, name="get_function_params"),
    path('delete-function', views.delete_imported_function, name='delete_imported_function'),
    
    # 手绘查询模板相关路由
    path('sketch-templates/save', views.save_sketch_template, name='save_sketch_template'),
    path('sketch-templates/list', views.get_sketch_templates, name='get_sketch_templates'),
    path('sketch-templates/delete', views.delete_sketch_template, name='delete_sketch_template'),
]