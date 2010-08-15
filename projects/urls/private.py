from django.conf.urls.defaults import *

urlpatterns = patterns('projects.views.private',
    url(r'^$',
        'project_dashboard',
        name='projects_dashboard'
    ),
    url(r'^create/$',
        'project_create',
        name='projects_create'
    ),
    url(r'^import/$',
        'project_import',
        name='projects_import'
    ),
    url(r'^(?P<project_slug>[-\w]+)/$',
        'project_manage',
        name='projects_manage'
    ),
    url(r'^(?P<project_slug>[-\w]+)/configure/$',
        'project_configure',
        name='projects_configure'
    ),
    url(r'^(?P<project_slug>[-\w]+)/edit/$',
        'project_edit',
        name='projects_edit'
    ),
    url(r'^(?P<project_slug>[-\w]+)/delete/$',
        'project_delete',
        name='projects_delete'
    ),
    url(r'^(?P<project_slug>[-\w]+)/add/$',
        'file_add',
        name='projects_file_add'
    ),
    url(r'^(?P<project_slug>[-\w]+)/(?P<file_id>\d+)/edit/$',
        'file_edit',
        name='projects_file_edit'
    ),
    url(r'^(?P<project_slug>[-\w]+)/(?P<file_id>\d+)/history/$',
        'file_history',
        name='projects_file_history'
    ),
    url(r'^(?P<project_slug>[-\w]+)/(?P<file_id>\d+)/diff/(?P<from_id>\d+)/(?P<to_id>\d+)/$',
        'file_diff',
        name='projects_file_diff'
    ),
    url(r'^(?P<project_slug>[-\w]+)/(?P<file_id>\d+)/delete/$',
        'file_delete',
        name='projects_file_delete'
    ),
)
