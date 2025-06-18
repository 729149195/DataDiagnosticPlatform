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
    path('get-shot-statistics', views.get_shot_statistics, name='get_shot_statistics'),

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
    
    # 系统监控状态
    path('system-monitor-status', views.get_system_monitor_status, name='get_system_monitor_status'),

    # 算法管理相关路由
    path('algorithm-channel-map', views.get_algorithm_channel_map, name='get_algorithm_channel_map'),
    path('algorithm-channel-category', views.create_algorithm_channel_category, name='create_algorithm_channel_category'),
    path('algorithm-channel-category/<str:category_name>', views.delete_algorithm_channel_category, name='delete_algorithm_channel_category'),
    path('algorithm-channel-algorithm', views.create_algorithm_channel_algorithm, name='create_algorithm_channel_algorithm'),
    path('algorithm-channel-algorithm/<str:category_name>/<str:algorithm_name>', views.delete_algorithm_channel_algorithm, name='delete_algorithm_channel_algorithm'),
    path('algorithm-channel-channels', views.create_algorithm_channel_channels, name='create_algorithm_channel_channels'),
    path('algorithm-channel-channels/<str:category_name>/<str:algorithm_name>/<str:channel_name>', views.delete_algorithm_channel_channel, name='delete_algorithm_channel_channel'),
    path('algorithm-upload-files', views.upload_algorithm_files, name='upload_algorithm_files'),
    path('import-algorithm-to-detection', views.import_algorithm_to_detection, name='import_algorithm_to_detection'),
]