# clm_service/urls.py
from django.urls import path
from . import views

urlpatterns = [
    
    # Création de contrat
    path('contrats/create/', views.create_contract_simple, name='create_contrat'),
    path('contrats/create-from-pdf/', views.create_contract_from_pdf, name='create_contract_from_pdf'),



    path('contrats/upload/',                     views.upload_contrat_pdf,     name='upload-contrat'),
    path('contrats/formulaire/',  views.create_contrat_formulaire, name='create-contrat-formulaire'),
    path('contrats/<int:contrat_id>/pdf/', views.generer_pdf_contrat, name='generer-pdf-contrat'),
    path('contrats/',          views.list_contrats,   name='list-contrats'),
    path('dashboard/stats/', views.dashboard_stats, name='dashboard-stats'),
    path('contrats/<int:contrat_id>/', views.detail_contrat, name='detail-contrat'),
    path('contrats/<int:contrat_id>/analyser/', views.analyser_contrat, name='analyser_contrat'),
    path('contrats/<int:contrat_id>/alertes/',  views.get_alertes_contrat, name='alertes_contrat'),





    path('contrats/<int:contrat_id>/risques/',   views.list_risques_contrat,    name='risques-contrat'),
    
    # Liste et détails
    # path('contrats/', views.list_my_contrats, name='list_contrats'),
    # path('contrats/<int:contrat_id>/', views.get_contrat_detail, name='contrat_detail'),
    
    # Modification et soumission
    path('contrats/<int:contrat_id>/update/', views.update_contrat, name='update_contrat'),
    path('contrats/<int:contrat_id>/submit/', views.submit_contrat, name='submit_contrat'),
]