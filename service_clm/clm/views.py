# clm_service/views.py
from django.shortcuts import render
from django.utils import timezone
from datetime import datetime
import json
import requests

from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework import status

from .authentication import RemoteJWTAuthentication
from .permissions import IsResponsableDepartement
from .models import Contrat
# Nouveaux imports pour PDF/OCR
import cloudinary.uploader
from .ocr_utils import extract_text_from_pdf
from .contract_parser import parse_contract_data

def get_user_info_from_auth(token):
    """
    Récupère les informations utilisateur depuis le service d'authentification
    Endpoint: /auth/me
    """
    try:
        from .discovery import get_auth_base_url
        
        auth_url = get_auth_base_url()
        url = f"{auth_url}/auth/me"
        headers = {'Authorization': f'Bearer {token}'}
        
        print(f'[CLM] 🔍 Appel Auth: {url}')
        
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            user_data = response.json()
            print(f'[CLM] ✅ Utilisateur trouvé: {user_data.get("email")}')
            return user_data
        else:
            print(f'[CLM] ❌ Auth error: {response.status_code}')
            return None
            
    except Exception as e:
        print(f'[CLM] ❌ Exception Auth: {str(e)}')
        return None


def get_direction_centrale_from_juridique(direction_id, token):
    """
    Récupère la direction centrale depuis le service juridique
    Endpoint: /juridique/directions/{direction_id}/
    """
    try:
        from .discovery import get_juridique_base_url
        import requests

        juridique_url = get_juridique_base_url()
        url = f"{juridique_url}/juridique/directions/{direction_id}/"

        headers = {
            'Authorization': f'Bearer {token}'
        }

        print(f'[CLM] 🔍 Appel Juridique: {url}')

        response = requests.get(url, headers=headers, timeout=5)

        if response.status_code == 200:
            response_data = response.json()

            # data
            direction_data = response_data.get('data', {})

            # directionCentrale object
            direction_centrale = direction_data.get('directionCentrale', {})

            # _id
            direction_centrale_id = direction_centrale.get('_id')

            print(f'[CLM] ✅ Direction centrale trouvée: {direction_centrale_id}')

            return direction_centrale_id

        else:
            print(f'[CLM] ⚠️ Juridique error: {response.status_code}')
            return None

    except Exception as e:
        print(f'[CLM] ❌ Exception Juridique: {str(e)}')
        return None


@api_view(['POST'])
@authentication_classes([RemoteJWTAuthentication])
@permission_classes([IsResponsableDepartement])
def create_contract_simple(request):
    """
    Création simple d'un contrat via formulaire POST
    1. Récupère les infos user depuis /auth/me
    2. Récupère direction_centrale_id depuis service juridique (optionnel)
    3. Crée le contrat
    """
    try:
        # 1. Récupérer le token
        token = request.auth
        if not token:
            return Response(
                {'error': 'Token non fourni'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # 2. Appeler le service Auth pour obtenir les infos utilisateur
        user_info = get_user_info_from_auth(token)
        
        if not user_info:
            return Response(
                {'error': 'Impossible de récupérer les informations utilisateur'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # 3. Extraire les informations nécessaires
        departement_id = user_info.get('departement_id')
        direction_id = user_info.get('direction_id')
        
        if not departement_id:
            return Response(
                {'error': 'Aucun département associé à cet utilisateur'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 4. Optionnel: Récupérer direction_centrale_id depuis service juridique
        direction_centrale_id = None
        if direction_id:
            direction_centrale_id = get_direction_centrale_from_juridique(direction_id, token)
        
        # 5. Valider les données du formulaire
        data = request.data
        
        required_fields = ['numero_contrat', 'titre', 'type_contrat', 
                          'partie_b_nom', 'pays_partie_b', 'objet',
                          'date_signature', 'date_debut', 'date_fin', 'montant']
        
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return Response(
                {'error': f'Champs manquants: {", ".join(missing_fields)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 6. Vérifier unicité du numéro de contrat
        if Contrat.objects.filter(numero_contrat=data.get('numero_contrat')).exists():
            return Response(
                {'error': 'Un contrat avec ce numéro existe déjà'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 7. Valider les dates
        try:
            date_signature = datetime.strptime(data.get('date_signature'), '%Y-%m-%d').date()
            date_debut = datetime.strptime(data.get('date_debut'), '%Y-%m-%d').date()
            date_fin = datetime.strptime(data.get('date_fin'), '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Format de date invalide. Utilisez YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if date_debut > date_fin:
            return Response(
                {'error': 'La date de début doit être antérieure à la date de fin'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if date_signature > date_debut:
            return Response(
                {'error': 'La date de signature doit être antérieure à la date de début'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 8. Créer le contrat
        contrat = Contrat.objects.create(
            # Données du formulaire
            numero_contrat=data.get('numero_contrat'),
            titre=data.get('titre'),
            type_contrat=data.get('type_contrat'),
            partie_a_nom=data.get('partie_a_nom', 'SONATRACH'),
            partie_b_nom=data.get('partie_b_nom'),
            pays_partie_b=data.get('pays_partie_b'),
            objet=data.get('objet'),
            date_signature=date_signature,
            date_debut=date_debut,
            date_fin=date_fin,
            montant=data.get('montant'),
            devise=data.get('devise', 'DZD'),
            conditions_paiement=data.get('conditions_paiement', ''),
            
            # Données du service Auth
            cree_par_id=user_info.get('id'),
            cree_par_role=user_info.get('role', 'responsable_departement'),
            departement_id=departement_id,
            direction_id=direction_id,
            
            # Données du service Juridique
            direction_centrale_id=direction_centrale_id,
            
            # Statut initial
            statut='brouillon'
        )
        
        # 9. Retourner la réponse
        return Response(
            {
                'success': True,
                'message': 'Contrat créé avec succès',
                'contrat': {
                    'id': contrat.id,
                    'numero_contrat': contrat.numero_contrat,
                    'titre': contrat.titre,
                    'type_contrat': contrat.get_type_contrat_display(),
                    'type_contrat_code': contrat.type_contrat,
                    'partie_b_nom': contrat.partie_b_nom,
                    'pays_partie_b': contrat.pays_partie_b,
                    'type_partie': contrat.type_partie,
                    'is_international': contrat.is_international,
                    'montant': float(contrat.montant),
                    'devise': contrat.devise,
                    'date_debut': contrat.date_debut,
                    'date_fin': contrat.date_fin,
                    'date_signature': contrat.date_signature,
                    'statut': contrat.get_statut_display(),
                    'statut_code': contrat.statut,
                    'date_creation': contrat.date_creation,
                    'cree_par_id': contrat.cree_par_id,
                    'cree_par_role': contrat.cree_par_role,
                    'departement_id': contrat.departement_id,
                    'direction_id': contrat.direction_id,
                    'direction_centrale_id': contrat.direction_centrale_id
                }
            },
            status=status.HTTP_201_CREATED
        )
        
    except Exception as e:
        return Response(
            {
                'success': False,
                'error': f'Erreur lors de la création du contrat: {str(e)}'
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@authentication_classes([RemoteJWTAuthentication])
@permission_classes([IsResponsableDepartement])
def get_current_user_info(request):
    """
    Endpoint pour tester la récupération des infos utilisateur depuis Auth
    Utile pour le débogage
    """
    try:
        token = request.auth
        user_info = get_user_info_from_auth(token)
        
        if user_info:
            return Response({
                'success': True,
                'user_info': user_info
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': 'Impossible de récupérer les informations'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([RemoteJWTAuthentication])
@permission_classes([IsResponsableDepartement])
def list_my_contrats(request):
    """
    Liste tous les contrats du département de l'utilisateur
    """
    try:
        token = request.auth
        user_info = get_user_info_from_auth(token)
        
        if not user_info:
            return Response(
                {'error': 'Utilisateur non trouvé'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        departement_id = user_info.get('departement_id')
        
        if not departement_id:
            return Response(
                {'error': 'Département non trouvé'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        contrats = Contrat.objects.filter(
            departement_id=departement_id
        ).order_by('-date_creation')
        
        contrats_list = []
        for contrat in contrats:
            contrats_list.append({
                'id': contrat.id,
                'numero_contrat': contrat.numero_contrat,
                'titre': contrat.titre,
                'type_contrat': contrat.get_type_contrat_display(),
                'partie_b_nom': contrat.partie_b_nom,
                'montant': f"{contrat.montant:,.2f} {contrat.devise}",
                'date_debut': contrat.date_debut,
                'date_fin': contrat.date_fin,
                'statut': contrat.get_statut_display(),
                'statut_code': contrat.statut,
                'date_creation': contrat.date_creation,
                'is_international': contrat.is_international
            })
        
        return Response({
            'success': True,
            'total': len(contrats_list),
            'departement_id': departement_id,
            'contrats': contrats_list
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@authentication_classes([RemoteJWTAuthentication])
@permission_classes([IsResponsableDepartement])
def get_contrat_detail(request, contrat_id):
    """
    Récupère les détails d'un contrat spécifique
    """
    try:
        token = request.auth
        user_info = get_user_info_from_auth(token)
        
        if not user_info:
            return Response(
                {'error': 'Utilisateur non trouvé'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        departement_id = user_info.get('departement_id')
        
        try:
            contrat = Contrat.objects.get(
                id=contrat_id,
                departement_id=departement_id
            )
        except Contrat.DoesNotExist:
            return Response(
                {'error': 'Contrat non trouvé ou accès non autorisé'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response({
            'success': True,
            'contrat': {
                'id': contrat.id,
                'numero_contrat': contrat.numero_contrat,
                'titre': contrat.titre,
                'type_contrat': contrat.get_type_contrat_display(),
                'type_contrat_code': contrat.type_contrat,
                'partie_a_nom': contrat.partie_a_nom,
                'partie_b_nom': contrat.partie_b_nom,
                'pays_partie_b': contrat.pays_partie_b,
                'type_partie': contrat.type_partie,
                'is_international': contrat.is_international,
                'objet': contrat.objet,
                'date_signature': contrat.date_signature,
                'date_debut': contrat.date_debut,
                'date_fin': contrat.date_fin,
                'montant': float(contrat.montant),
                'devise': contrat.devise,
                'conditions_paiement': contrat.conditions_paiement,
                'statut': contrat.get_statut_display(),
                'statut_code': contrat.statut,
                'date_creation': contrat.date_creation,
                'date_modification': contrat.date_modification,
                'cree_par_id': contrat.cree_par_id,
                'cree_par_role': contrat.cree_par_role,
                'departement_id': contrat.departement_id,
                'direction_id': contrat.direction_id,
                'direction_centrale_id': contrat.direction_centrale_id
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT'])
@authentication_classes([RemoteJWTAuthentication])
@permission_classes([IsResponsableDepartement])
def update_contrat(request, contrat_id):
    """
    Met à jour un contrat (seulement en statut brouillon)
    """
    try:
        token = request.auth
        user_info = get_user_info_from_auth(token)
        
        if not user_info:
            return Response(
                {'error': 'Utilisateur non trouvé'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        departement_id = user_info.get('departement_id')
        
        try:
            contrat = Contrat.objects.get(
                id=contrat_id,
                departement_id=departement_id
            )
        except Contrat.DoesNotExist:
            return Response(
                {'error': 'Contrat non trouvé ou accès non autorisé'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if contrat.statut != 'brouillon':
            return Response(
                {'error': f'Impossible de modifier un contrat en statut {contrat.get_statut_display()}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = request.data
        updatable_fields = ['titre', 'type_contrat', 'partie_b_nom', 'pays_partie_b',
                           'objet', 'date_signature', 'date_debut', 'date_fin',
                           'montant', 'devise', 'conditions_paiement']
        
        for field in updatable_fields:
            if field in data:
                setattr(contrat, field, data[field])
        
        contrat.save()
        
        return Response({
            'success': True,
            'message': 'Contrat mis à jour avec succès',
            'contrat': {
                'id': contrat.id,
                'numero_contrat': contrat.numero_contrat,
                'titre': contrat.titre,
                'statut': contrat.get_statut_display()
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@authentication_classes([RemoteJWTAuthentication])
@permission_classes([IsResponsableDepartement])
def submit_contrat(request, contrat_id):
    """
    Soumet le contrat pour validation (brouillon -> actif)
    """
    try:
        token = request.auth
        user_info = get_user_info_from_auth(token)
        
        if not user_info:
            return Response(
                {'error': 'Utilisateur non trouvé'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        departement_id = user_info.get('departement_id')
        
        try:
            contrat = Contrat.objects.get(
                id=contrat_id,
                departement_id=departement_id,
                statut='brouillon'
            )
        except Contrat.DoesNotExist:
            return Response(
                {'error': 'Contrat non trouvé ou déjà soumis'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        contrat.statut = 'actif'
        contrat.save()
        
        return Response({
            'success': True,
            'message': 'Contrat soumis avec succès',
            'contrat': {
                'id': contrat.id,
                'numero_contrat': contrat.numero_contrat,
                'statut': contrat.get_statut_display()
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
@api_view(['POST'])
@authentication_classes([RemoteJWTAuthentication])
@permission_classes([IsResponsableDepartement])
def create_contract_from_pdf(request):
    """
    Création d'un contrat par upload de PDF (avec OCR si scanné).
    
    Requête : multipart/form-data
    ┌─────────────────────────────────────────────────────┐
    │  Champ        │ Type         │ Description           │
    ├─────────────────────────────────────────────────────┤
    │  pdf_file     │ File (PDF)   │ Obligatoire           │
    │  auto_fill    │ bool (str)   │ "true" = parser le PDF│
    │  [autres]     │ string       │ Override manuel        │
    └─────────────────────────────────────────────────────┘
    
    Flux :
      1. Validation du fichier (type, taille)
      2. Récupération des infos utilisateur (Auth)
      3. Extraction du texte (PyMuPDF → Tesseract si besoin)
      4. Upload sur Cloudinary
      5. Parsing des données (si auto_fill=true)
      6. Merge données parsées + données manuelles
      7. Création du contrat en base
    """
    try:
        # ── 1. Récupérer le token et les infos user ────────────────────────
        token = request.auth
        if not token:
            return Response(
                {'error': 'Token non fourni'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        user_info = get_user_info_from_auth(token)
        if not user_info:
            return Response(
                {'error': 'Impossible de récupérer les informations utilisateur'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        departement_id  = user_info.get('departement_id')
        direction_id    = user_info.get('direction_id')

        if not departement_id:
            return Response(
                {'error': 'Aucun département associé à cet utilisateur'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── 2. Valider le fichier PDF ──────────────────────────────────────
        pdf_file = request.FILES.get('pdf_file')
        if not pdf_file:
            return Response(
                {'error': 'Aucun fichier PDF fourni (champ : pdf_file)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Vérifier l'extension
        import os
        _, ext = os.path.splitext(pdf_file.name.lower())
        if ext not in ['.pdf']:
            return Response(
                {'error': f'Format non supporté : {ext}. Seuls les PDF sont acceptés.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Vérifier la taille
        from django.conf import settings as django_settings
        max_size = getattr(django_settings, 'PDF_MAX_SIZE_BYTES', 10 * 1024 * 1024)
        if pdf_file.size > max_size:
            max_mb = max_size / (1024 * 1024)
            return Response(
                {'error': f'Fichier trop volumineux. Maximum : {max_mb:.0f} MB'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Lire les bytes du PDF
        pdf_bytes = pdf_file.read()

        # ── 3. Extraire le texte (natif ou OCR) ───────────────────────────
        print(f'[CLM-PDF] 🔍 Extraction texte du PDF : {pdf_file.name}')
        extraction_result = extract_text_from_pdf(pdf_bytes)

        extracted_text = ''
        extraction_info = {
            'method': extraction_result.get('method'),
            'pages':  extraction_result.get('pages'),
            'chars':  len(extraction_result.get('text', '')),
        }

        if extraction_result['success']:
            extracted_text = extraction_result['text']
            print(f'[CLM-PDF] ✅ Texte extrait ({extraction_info["method"]}) : '
                  f'{extraction_info["chars"]} caractères sur {extraction_info["pages"]} pages')
        else:
            print(f'[CLM-PDF] ⚠️ Extraction échouée : {extraction_result.get("error")}')

        # ── 4. Uploader le PDF sur Cloudinary ─────────────────────────────
        folder = getattr(django_settings, 'CLOUDINARY_CONTRACTS_FOLDER', 'contrats_pdf')
        cloudinary_result = None
        pdf_url = None

        try:
            # Rembobiner le fichier avant l'upload
            pdf_file.seek(0)
            cloudinary_result = cloudinary.uploader.upload(
                pdf_file,
                folder=folder,
                resource_type='raw',   # 'raw' pour les PDFs
                use_filename=True,
                unique_filename=True,
            )
            pdf_url = cloudinary_result.get('secure_url')
            print(f'[CLM-PDF] ☁️ PDF uploadé sur Cloudinary : {pdf_url}')
        except Exception as e:
            print(f'[CLM-PDF] ⚠️ Upload Cloudinary échoué : {str(e)}')
            # Non bloquant : on continue sans URL

        # ── 5. Parser les données (si auto_fill=true) ─────────────────────
        parsed_data = {}
        auto_fill = request.data.get('auto_fill', 'true').lower() == 'true'

        if auto_fill and extracted_text:
            parsed_data = parse_contract_data(extracted_text)
            print(f'[CLM-PDF] 📊 Données parsées : '
                  f'{[k for k, v in parsed_data.items() if v]}')

        # ── 6. Merge : données parsées < données manuelles ────────────────
        # Les données envoyées manuellement dans la requête ont la priorité
        data = request.data  # données du formulaire multipart

        def get_field(field_name, default=None):
            """Priorité : manuel > parsé > défaut"""
            manual = data.get(field_name)
            if manual not in [None, '']:
                return manual
            parsed = parsed_data.get(field_name)
            if parsed not in [None, '']:
                return parsed
            return default

        # ── 7. Valider les champs obligatoires ────────────────────────────
        numero_contrat      = get_field('numero_contrat')
        titre               = get_field('titre')
        type_contrat        = get_field('type_contrat', 'autre')
        partie_b_nom        = get_field('partie_b_nom')
        pays_partie_b       = get_field('pays_partie_b', 'Algérie')
        objet               = get_field('objet')
        date_signature_str  = get_field('date_signature')
        date_debut_str      = get_field('date_debut')
        date_fin_str        = get_field('date_fin')
        montant             = get_field('montant')

        # Champs obligatoires pour créer le contrat
        missing = []
        if not numero_contrat:  missing.append('numero_contrat')
        if not titre:           missing.append('titre')
        if not partie_b_nom:    missing.append('partie_b_nom')
        if not objet:           missing.append('objet')
        if not date_signature_str: missing.append('date_signature')
        if not date_debut_str:  missing.append('date_debut')
        if not date_fin_str:    missing.append('date_fin')
        if not montant:         missing.append('montant')

        if missing:
            return Response(
                {
                    'error': f'Champs manquants (non trouvés dans le PDF ni fournis manuellement) : '
                             f'{", ".join(missing)}',
                    'tip': 'Envoyez ces champs dans le formulaire multipart pour les compléter.',
                    'parsed_data': parsed_data,  # retourner ce qui a été trouvé
                    'extraction_info': extraction_info,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── 8. Vérifier unicité ───────────────────────────────────────────
        if Contrat.objects.filter(numero_contrat=numero_contrat).exists():
            return Response(
                {'error': f'Un contrat avec le numéro {numero_contrat} existe déjà'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── 9. Parser les dates ───────────────────────────────────────────
        try:
            from datetime import datetime
            date_signature = datetime.strptime(date_signature_str, '%Y-%m-%d').date()
            date_debut     = datetime.strptime(date_debut_str,     '%Y-%m-%d').date()
            date_fin       = datetime.strptime(date_fin_str,       '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Format de date invalide. Attendu : YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if date_debut > date_fin:
            return Response(
                {'error': 'date_debut doit être avant date_fin'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── 10. Récupérer direction_centrale_id (optionnel) ───────────────
        direction_centrale_id = None
        if direction_id:
            direction_centrale_id = get_direction_centrale_from_juridique(direction_id, token)

        # ── 11. Créer le contrat ──────────────────────────────────────────
        contrat = Contrat.objects.create(
            numero_contrat         = numero_contrat,
            titre                  = titre,
            type_contrat           = type_contrat,
            partie_a_nom           = get_field('partie_a_nom', 'SONATRACH'),
            partie_b_nom           = partie_b_nom,
            pays_partie_b          = pays_partie_b,
            objet                  = objet,
            date_signature         = date_signature,
            date_debut             = date_debut,
            date_fin               = date_fin,
            montant                = float(montant),
            devise                 = get_field('devise', 'DZD'),
            conditions_paiement    = get_field('conditions_paiement', ''),

            # Infos utilisateur
            cree_par_id            = user_info.get('id'),
            cree_par_role          = user_info.get('role', 'responsable_departement'),
            departement_id         = departement_id,
            direction_id           = direction_id,
            direction_centrale_id  = direction_centrale_id,

            statut                 = 'brouillon',

            # URL du PDF (si ton modèle a ce champ — voir note ci-dessous)
            pdf_url              = pdf_url,
        )

        # ── 12. Réponse ───────────────────────────────────────────────────
        return Response(
            {
                'success': True,
                'message': 'Contrat créé avec succès depuis le PDF',
                'pdf_info': {
                    'filename':         pdf_file.name,
                    'size_kb':          round(pdf_file.size / 1024, 1),
                    'cloudinary_url':   pdf_url,
                    'extraction_method': extraction_info['method'],
                    'pages':            extraction_info['pages'],
                    'chars_extracted':  extraction_info['chars'],
                },
                'contrat': {
                    'id':               contrat.id,
                    'numero_contrat':   contrat.numero_contrat,
                    'titre':            contrat.titre,
                    'type_contrat':     contrat.get_type_contrat_display(),
                    'partie_b_nom':     contrat.partie_b_nom,
                    'pays_partie_b':    contrat.pays_partie_b,
                    'is_international': contrat.is_international,
                    'montant':          float(contrat.montant),
                    'devise':           contrat.devise,
                    'date_debut':       contrat.date_debut,
                    'date_fin':         contrat.date_fin,
                    'date_signature':   contrat.date_signature,
                    'statut':           contrat.get_statut_display(),
                    'statut_code':      contrat.statut,
                    'date_creation':    contrat.date_creation,
                    'departement_id':   contrat.departement_id,
                }
            },
            status=status.HTTP_201_CREATED
        )

    except Exception as e:
        import traceback
        print(f'[CLM-PDF] ❌ Exception : {traceback.format_exc()}')
        return Response(
            {
                'success': False,
                'error': f'Erreur serveur : {str(e)}'
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
# clm/views.py — vue upload_contrat_pdf mise à jour

from .risk_engine import analyser_risques, get_niveau_escalade
from .models import Contrat, MetadonneeContrat, RisqueContrat
from django.utils import timezone


def _save_metadonnees(contrat, metadonnees: dict):
    for cle, valeur in metadonnees.items():
        if valeur is not None:
            MetadonneeContrat.objects.update_or_create(
                contrat=contrat,
                cle=cle,
                defaults={'valeur': str(valeur)}
            )


def _save_risques(contrat, risques_detectes: list) -> list:
    """
    Sauvegarde les risques détectés.
    Si un risque (même code) existe déjà → incrémente occurrence_count
    et recalcule le niveau d'escalade.
    Retourne la liste enrichie avec niveau_escalade.
    """
    saved = []
    for r in risques_detectes:
        existing = RisqueContrat.objects.filter(
            contrat=contrat,
            code=r['code'],
            resolu=False
        ).first()

        if existing:
            existing.occurrence_count += 1
            escalade = get_niveau_escalade(existing.occurrence_count)
            existing.niveau_alerte = escalade['niveau']
            existing.save()
            r['occurrence_count'] = existing.occurrence_count
            r['niveau_alerte']    = escalade
        else:
            escalade = get_niveau_escalade(1)
            obj = RisqueContrat.objects.create(
                contrat          = contrat,
                code             = r['code'],
                type_risque      = r['type'],
                description      = r['description'],
                severite         = r['severite'],
                article_ref      = r.get('article_ref', ''),
                suggestion       = r.get('suggestion', ''),
                occurrence_count = 1,
                niveau_alerte    = escalade['niveau'],
            )
            r['occurrence_count'] = 1
            r['niveau_alerte']    = escalade

        saved.append(r)
    return saved

# clm/views.py  — Ajouter cette fonction AVANT upload_contrat_pdf

# ══════════════════════════════════════════════════════════════
# HELPERS — à coller JUSTE AVANT upload_contrat_pdf
# ══════════════════════════════════════════════════════════════

# def _merge_parsed_with_form(parsed: dict, form_data) -> dict:
#     """
#     Fusionne les données parsées depuis le PDF avec les données
#     envoyées manuellement via le formulaire.
#     Règle : form_data écrase parsed si la valeur est non-vide.
#     """
#     merged = dict(parsed)

#     FORM_FIELDS = [
#         'numero_contrat', 'titre', 'type_contrat',
#         'societe_a_nom', 'societe_b_nom', 'pays_partie_b',
#         'objet', 'date_signature', 'date_debut', 'date_fin',
#         'montant', 'devise', 'conditions_paiement',
#         # Représentants
#         'societe_a_representant_nom', 'societe_a_representant_prenom',
#         'societe_a_representant_fonction', 'societe_b_siege_social',
#         'societe_b_representant_nom', 'societe_b_representant_prenom',
#         'societe_b_representant_fonction',
#         # Contacts Art. 21
#         'notification_adresse_ligne1', 'notification_adresse_ligne2',
#         'fax_fournisseur', 'telephone_fournisseur', 'email_fournisseur',
#         # Signatures Art. 22
#         'nom_client', 'prenom_client', 'fonction_client',
#         'nom_fournisseur', 'prenom_fournisseur', 'fonction_fournisseur',
#     ]

#     for field in FORM_FIELDS:
#         value = form_data.get(field)
#         if value not in (None, '', [], {}):
#             merged[field] = value

#     return merged
def _merge_parsed_with_form(parsed: dict, form_data) -> dict:
    """
    Fusionne les données parsées depuis le PDF avec les données
    envoyées manuellement via le formulaire.
    Règle : form_data écrase parsed si la valeur est non-vide.
    """
    merged = dict(parsed)

    FORM_FIELDS = [
        'numero_contrat', 'titre', 'type_contrat',
        'societe_a_nom', 'societe_b_nom', 'pays_partie_b',
        'objet', 'date_signature', 'date_debut', 'date_fin',
        'montant', 'devise', 'conditions_paiement',
        # Représentants
        'societe_a_representant_nom', 'societe_a_representant_prenom',
        'societe_a_representant_fonction', 'societe_b_siege_social',
        'societe_b_representant_nom', 'societe_b_representant_prenom',
        'societe_b_representant_fonction',
        # Contacts Art. 21
        'notification_adresse_ligne1', 'notification_adresse_ligne2',
        'fax_fournisseur', 'telephone_fournisseur', 'email_fournisseur',
        # Signatures Art. 22
        'nom_client', 'prenom_client', 'fonction_client',
        'nom_fournisseur', 'prenom_fournisseur', 'fonction_fournisseur',
        # Délai de livraison — NOUVEAU
        'delai_livraison_mois',
    ]

    for field in FORM_FIELDS:
        value = form_data.get(field)
        if value not in (None, '', [], {}):
            merged[field] = value

    return merged

def _validate_dates(merged: dict) -> list:
    """
    Valide la cohérence des dates du contrat.
    Retourne une liste d'erreurs (vide si tout est OK).
    """
    import datetime as dt

    errors = []

    def parse_date(val):
        if val is None:
            return None
        if isinstance(val, dt.date):
            return val
        if isinstance(val, dt.datetime):
            return val.date()
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
            try:
                return dt.datetime.strptime(str(val).strip(), fmt).date()
            except ValueError:
                continue
        return None

    d_signature = parse_date(merged.get('date_signature'))
    d_debut     = parse_date(merged.get('date_debut'))
    d_fin       = parse_date(merged.get('date_fin'))

    if d_debut and d_fin and d_debut > d_fin:
        errors.append(
            f"La date de début ({d_debut}) ne peut pas être "
            f"postérieure à la date de fin ({d_fin})."
        )

    if d_signature and d_debut and d_signature > d_debut:
        errors.append(
            f"La date de signature ({d_signature}) ne peut pas être "
            f"postérieure à la date de début ({d_debut})."
        )

    return errors


def _save_metadonnees(contrat, metadonnees: dict):
    """Sauvegarde les métadonnées clé-valeur liées au contrat."""
    from .models import MetadonneeContrat
    for cle, valeur in metadonnees.items():
        if valeur not in (None, '', {}, []):
            MetadonneeContrat.objects.update_or_create(
                contrat=contrat,
                cle=str(cle),
                defaults={'valeur': str(valeur)},
            )


def _save_risques(contrat, risques_bruts: list) -> list:
    """Sauvegarde les risques détectés et retourne la liste sérialisée."""
    from .models import RisqueContrat
    sauves = []
    for r in risques_bruts:
        obj, _ = RisqueContrat.objects.update_or_create(
            contrat=contrat,
            code=r.get('code', ''),
            defaults={
                'type_risque':      r.get('type', 'imprecision'),
                'description':      r.get('description', ''),
                'severite':         r.get('severite', 'faible'),
                'article_ref':      r.get('article_ref', ''),
                'suggestion':       r.get('suggestion', ''),
                'niveau_alerte':    r.get('niveau_alerte', 'warning'),
                'occurrence_count': r.get('occurrence_count', 1),
                'resolu':           False,
            }
        )
        sauves.append({
            'id':          obj.id,
            'code':        obj.code,
            'type':        obj.type_risque,
            'description': obj.description,
            'severite':    obj.severite,
            'article_ref': obj.article_ref,
            'suggestion':  obj.suggestion,
        })
    return sauves

from .risk_engine import (
    analyser_risques,
    TYPE_RETARD,
    TYPE_IMPRECISION,
    TYPE_DIFFERENT,
    SEV_CRITIQUE,
    SEV_ELEVE,
    SEV_MOYEN,
    SEV_FAIBLE,
)
from rest_framework.permissions import IsAuthenticated
@api_view(['POST'])
@authentication_classes([RemoteJWTAuthentication])
@permission_classes([IsResponsableDepartement])
def upload_contrat_pdf(request):
    """
    POST /clm/contrats/upload/

    Flux complet :
    1. Auth JWT → user_id, departement_id, direction_id
    2. direction_centrale_id depuis service Juridique (si absent du JWT)
    3. OCR / extraction texte (PyMuPDF natif ou Tesseract)
    4. Parse regex → champs standards + métadonnées spécifiques
    5. Fusion parser + corrections formulaire (formulaire prioritaire)
    6. Validation dates
    7. Création Contrat
    8. Sauvegarde MetadonneeContrat
    9. Analyse de risques → création RisqueContrat
    10. Réponse 201 avec rapport complet
    """
    import io, uuid, logging
    from datetime import datetime

    logger = logging.getLogger(__name__)

    try:
        # ── Auth ──────────────────────────────────────────────────────
        token = request.auth
        if not token:
            return Response({'error': 'Token non fourni'}, status=401)

        user_info = get_user_info_from_auth(token)
        if not user_info:
            return Response({'error': 'Utilisateur non trouvé'}, status=401)

        departement_id = user_info.get('departement_id')
        direction_id   = user_info.get('direction_id')
        if not departement_id:
            return Response({'error': 'Aucun département associé'}, status=400)

        direction_centrale_id = user_info.get('direction_centrale_id')
        if not direction_centrale_id and direction_id:
            direction_centrale_id = get_direction_centrale_from_juridique(direction_id, token)

        # ── Fichier ───────────────────────────────────────────────────
        fichier = request.FILES.get('fichier')
        if not fichier:
            return Response({'error': 'Aucun fichier fourni'}, status=400)

        ext = fichier.name.rsplit('.', 1)[-1].lower()
        if ext not in ['pdf', 'docx', 'png', 'jpg', 'jpeg', 'tiff', 'tif']:
            return Response({'error': f'Format non supporté : {ext}'}, status=400)

        # ── OCR ───────────────────────────────────────────────────────
        pdf_bytes = fichier.read()
        fichier.seek(0)

        ocr_result = extract_text_from_pdf(pdf_bytes)
        if not ocr_result['success']:
            return Response({'error': f"OCR échoué : {ocr_result.get('error')}"}, status=422)

        texte_extrait = ocr_result['text']

        # ── Parser ────────────────────────────────────────────────────
        parsed              = parse_contract_data(texte_extrait)
        metadonnees_parsees = parsed.pop('metadonnees', {})
        parsed.pop('risques_detectes', None)

        # ── Fusion avec formulaire ────────────────────────────────────
        merged = _merge_parsed_with_form(parsed, request.data)
        if not merged.get('numero_contrat'):
            merged['numero_contrat'] = f"SH-{datetime.now().year}-{uuid.uuid4().hex[:6].upper()}"

        # ── Validation ────────────────────────────────────────────────
        date_errors = _validate_dates(merged)
        if date_errors:
            return Response({'error': 'Erreurs dates', 'details': date_errors}, status=400)

        if Contrat.objects.filter(numero_contrat=merged['numero_contrat']).exists():
            return Response({'error': f"Numéro déjà existant : {merged['numero_contrat']}"}, status=409)

        
        # ── Délai de livraison → date limite (calcul automatique) ──────
        def _to_int_or_none(v):
            try:
                return int(v)
            except (TypeError, ValueError):
                return None

        delai_livraison_mois = _to_int_or_none(
            merged.get('delai_livraison_mois') or metadonnees_parsees.get('delai_livraison_mois')
        )
        from uuid import uuid4
        contrat = Contrat.objects.create(
            numero_contrat        = merged.get('numero_contrat') or f'CLM-{uuid4().hex[:8].upper()}',
            titre                 = merged.get('titre') or 'Contrat Fourniture',
            type_contrat          = merged.get('type_contrat') or 'fourniture',
            cree_par_id           = user_info['id'],
            cree_par_role         = user_info.get('role', ''),
            departement_id        = user_info.get('departement_id', ''),
            direction_id          = user_info.get('direction_id', ''),
            direction_centrale_id = user_info.get('direction_centrale_id', ''),

            # ── Parties — RENOMMÉS v2 ────────────────────────────────────
            societe_a_nom  = merged.get('societe_a_nom') or 'SONATRACH',   # ANCIEN: partie_a_nom
            societe_b_nom  = merged.get('societe_b_nom') or '',            # ANCIEN: partie_b_nom

            pays_partie_b  = merged.get('pays_partie_b') or 'Algérie',

            # ── Représentants ─────────────────────────────────────────────
            societe_a_representant_nom      = merged.get('societe_a_representant_nom'),
            societe_a_representant_prenom   = merged.get('societe_a_representant_prenom'),
            societe_a_representant_fonction = merged.get('societe_a_representant_fonction'),
            societe_b_siege_social          = merged.get('societe_b_siege_social'),
            societe_b_representant_nom      = merged.get('societe_b_representant_nom'),
            societe_b_representant_prenom   = merged.get('societe_b_representant_prenom'),
            societe_b_representant_fonction = merged.get('societe_b_representant_fonction'),

            # ── Contacts Art. 21 ─────────────────────────────────────────
            notification_adresse_ligne1 = merged.get('notification_adresse_ligne1'),
            notification_adresse_ligne2 = merged.get('notification_adresse_ligne2'),
            fax_fournisseur             = merged.get('fax_fournisseur'),
            telephone_fournisseur       = merged.get('telephone_fournisseur'),
            email_fournisseur           = merged.get('email_fournisseur'),

            # ── Signatures Art. 22 ───────────────────────────────────────
            nom_client           = merged.get('nom_client'),
            prenom_client        = merged.get('prenom_client'),
            fonction_client      = merged.get('fonction_client'),
            nom_fournisseur      = merged.get('nom_fournisseur'),
            prenom_fournisseur   = merged.get('prenom_fournisseur'),
            fonction_fournisseur = merged.get('fonction_fournisseur'),

            # ── Détails ───────────────────────────────────────────────────
            objet               = merged.get('objet') or '',
            date_signature      = merged.get('date_signature'),
            date_debut          = merged.get('date_debut'),
            date_fin            = merged.get('date_fin'),
            delai_livraison_mois = delai_livraison_mois,   # NOUVEAU — déclenche le calcul de date_limite_livraison dans save()
            
            montant             = merged.get('montant') or 0,
            devise              = merged.get('devise') or 'DZD',
            conditions_paiement = merged.get('conditions_paiement'),
            fichier_original    = fichier,
            fichier_format      = ext,
            texte_extrait       = texte_extrait,
            moteur_ocr          = ocr_result.get('method', ''),
            ocr_effectue        = True,
            ocr_date            = timezone.now(),
            statut              = 'brouillon',
        )

        # ── Métadonnées spécifiques ────────────────────────────────────
        # Fusionner avec les éventuelles corrections du formulaire
        for cle in metadonnees_parsees:
            val_form = request.data.get(cle)
            if val_form:
                metadonnees_parsees[cle] = val_form
        _save_metadonnees(contrat, metadonnees_parsees)

        # ── Analyse des risques ────────────────────────────────────────
        parsed_with_meta = dict(merged)
        parsed_with_meta['metadonnees'] = metadonnees_parsees
        risques_bruts  = analyser_risques(parsed_with_meta, texte_extrait)
        risques_sauves = _save_risques(contrat, risques_bruts)
        # ── Notification automatique des risques RETARD ────────────────
        # Lire les risques retard tels que sauvegardés en base Django
        # (même logique que analyser_contrat, pour garder occurrence_count
        # et le niveau d'escalade cohérents avec ce qui est déjà persisté)
        risques_retard_bdd = RisqueContrat.objects.filter(
            contrat=contrat,
            type_risque='retard',
            resolu=False,
        )

        risques_a_notifier = [
            {
                'code':             r.code,
                'type':             r.type_risque,
                'description':      r.description,
                'severite':         r.severite,
                'article_ref':      r.article_ref or '',
                'suggestion':       r.suggestion or '',
                'occurrence_count': r.occurrence_count,
                'escalade':         get_niveau_escalade(r.occurrence_count),
            }
            for r in risques_retard_bdd
        ]

        try:
            notif_result = envoyer_alertes_risque(contrat_id=contrat.id, risques=risques_a_notifier, jwt_token=token)
            logger.info(f'[UPLOAD] Notification risques retard → {notif_result}')
        except Exception as exc_notif:
            # Ne jamais faire échouer l'upload si la notification échoue
            logger.error(f'[UPLOAD] Échec notification risques retard : {exc_notif}', exc_info=True)
            notif_result = {'success': False, 'sent_count': 0, 'errors': [str(exc_notif)]}

        # ── Rapport ───────────────────────────────────────────────────
        champs_obligatoires = [
            'numero_contrat', 'titre', 'type_contrat',
            'partie_b_nom', 'pays_partie_b', 'objet',
            'date_signature', 'date_debut', 'date_fin', 'montant',
        ]
        champs_trouves   = [c for c in champs_obligatoires if merged.get(c)]
        champs_manquants = [c for c in champs_obligatoires if not merged.get(c)]

        risques_par_type = {
            TYPE_RETARD:      [r for r in risques_sauves if r['type'] == TYPE_RETARD],
            TYPE_IMPRECISION: [r for r in risques_sauves if r['type'] == TYPE_IMPRECISION],
            TYPE_DIFFERENT:   [r for r in risques_sauves if r['type'] == TYPE_DIFFERENT],
        }

        return Response({
            'success': True,
            'contrat': {
                'id':                    contrat.id,
                'numero_contrat':        contrat.numero_contrat,
                'titre':                 contrat.titre,
                'type_contrat':          contrat.get_type_contrat_display(),
                'type_contrat_code':     contrat.type_contrat,
                # 'partie_a_nom':          contrat.partie_a_nom,
                # 'partie_b_nom':          contrat.partie_b_nom,
                'partie_a_nom': contrat.societe_a_nom,
                'partie_b_nom': contrat.societe_b_nom,

                'pays_partie_b':         contrat.pays_partie_b,
                'type_partie':           contrat.type_partie,
                'is_international':      contrat.is_international,
                'montant':               float(contrat.montant),
                'devise':                contrat.devise,
                'date_debut':            contrat.date_debut,
                'date_fin':              contrat.date_fin,
                'delai_livraison_mois':   contrat.delai_livraison_mois,        # NOUVEAU
                'date_limite_livraison':  contrat.date_limite_livraison,       # NOUVEAU
                'jours_restants_livraison': contrat.jours_restants_livraison,  # NOUVEAU
                'est_en_retard':          contrat.est_en_retard,     
                'date_signature':        contrat.date_signature,
                'statut':                contrat.statut,
                'cree_par_id':           contrat.cree_par_id,
                'departement_id':        contrat.departement_id,
                'direction_id':          contrat.direction_id,
                'direction_centrale_id': contrat.direction_centrale_id,
                'date_creation':         contrat.date_creation,
            },
            'extraction': {
                'method':           ocr_result['method'],
                'pages':            ocr_result['pages'],
                'chars_extraits':   len(texte_extrait),
                'champs_trouves':   champs_trouves,
                'champs_manquants': champs_manquants,
                'metadonnees':      metadonnees_parsees,
            },
            'risques': {
                'total':          len(risques_sauves),
                'par_type':       {
                    'retard':      len(risques_par_type[TYPE_RETARD]),
                    'imprecision': len(risques_par_type[TYPE_IMPRECISION]),
                    'different':   len(risques_par_type[TYPE_DIFFERENT]),
                },
             'notification': notif_result,   # ← AJOUT : résultat de l'envoi vers Mongo/Node

                'critique_count': sum(1 for r in risques_sauves if r['severite'] == SEV_CRITIQUE),
                'detail':         risques_sauves,
            },
        }, status=201)

    except Exception as e:
        logger.error(f'[UPLOAD] {str(e)}', exc_info=True)
        return Response({'success': False, 'error': str(e)}, status=500)
    
# clm/views.py — Ajouter cette vue

@api_view(['POST'])
@authentication_classes([RemoteJWTAuthentication])
@permission_classes([IsResponsableDepartement])
def create_contrat_formulaire(request):
    """
    POST /clm/contrats/formulaire/

    Création manuelle d'un contrat via formulaire (sans OCR obligatoire).
    Le PDF est optionnel — s'il est fourni, il est stocké sans extraction.

    Flux :
    1. Auth JWT
    2. Validation des champs obligatoires
    3. Validation des dates
    4. Vérification unicité numéro contrat
    5. Création Contrat
    6. Sauvegarde MetadonneeContrat (pénalités, garantie, caution…)
    7. Analyse de risques
    8. Réponse 201
    """
    import uuid
    import logging
    from datetime import datetime

    logger = logging.getLogger(__name__)

    try:
        # ── Auth ──────────────────────────────────────────────────────
        token = request.auth
        if not token:
            return Response({'error': 'Token non fourni'}, status=401)

        user_info = get_user_info_from_auth(token)
        if not user_info:
            return Response({'error': 'Utilisateur non trouvé'}, status=401)

        departement_id = user_info.get('departement_id')
        direction_id   = user_info.get('direction_id')
        if not departement_id:
            return Response({'error': 'Aucun département associé'}, status=400)

        direction_centrale_id = user_info.get('direction_centrale_id')
        if not direction_centrale_id and direction_id:
            direction_centrale_id = get_direction_centrale_from_juridique(direction_id, token)

        data = request.data

        # ── Numéro contrat ────────────────────────────────────────────
        numero_contrat = data.get('numero_contrat') or \
            f"SH-{datetime.now().year}-{uuid.uuid4().hex[:6].upper()}"

        if Contrat.objects.filter(numero_contrat=numero_contrat).exists():
            return Response(
                {'error': f"Numéro déjà existant : {numero_contrat}"},
                status=409
            )

        # ── Validation champs obligatoires ────────────────────────────
        champs_obligatoires = {
            'titre':        data.get('titre'),
            'type_contrat': data.get('type_contrat'),
            'societe_b_nom': data.get('societe_b_nom') or data.get('partie_b_nom'),
            'objet':        data.get('objet'),
        }
        manquants = [c for c, v in champs_obligatoires.items() if not v]
        if manquants:
            return Response(
                {'error': 'Champs obligatoires manquants', 'details': manquants},
                status=400
            )

        # ── Validation type_contrat ───────────────────────────────────
        types_valides = ['service', 'fourniture', 'travaux', 'partenariat', 'vente', 'transfert']
        if data.get('type_contrat') not in types_valides:
            return Response(
                {'error': f"type_contrat invalide. Valeurs acceptées : {types_valides}"},
                status=400
            )

        # ── Validation dates ──────────────────────────────────────────
        merged_for_validation = {
            'date_signature': data.get('date_signature'),
            'date_debut':     data.get('date_debut'),
            'date_fin':       data.get('date_fin'),
        }
        date_errors = _validate_dates(merged_for_validation)
        if date_errors:
            return Response({'error': 'Erreurs dates', 'details': date_errors}, status=400)

        # ── Fichier PDF optionnel ─────────────────────────────────────
        fichier    = request.FILES.get('fichier')
        ext        = ''
        texte_extrait = ''
        if fichier:
            ext = fichier.name.rsplit('.', 1)[-1].lower()
            if ext not in ['pdf', 'docx', 'png', 'jpg', 'jpeg', 'tiff', 'tif']:
                return Response({'error': f'Format non supporté : {ext}'}, status=400)


        # ── Délai de livraison → date limite (calcul automatique) ──────
        try:
            delai_livraison_mois = int(data.get('delai_livraison_mois'))
        except (TypeError, ValueError):
            delai_livraison_mois = None

        # ── Création Contrat ──────────────────────────────────────────
        contrat = Contrat.objects.create(
            numero_contrat        = numero_contrat,
            titre                 = data.get('titre') or 'Contrat Fourniture',
            type_contrat          = data.get('type_contrat') or 'fourniture',
            cree_par_id           = user_info['id'],
            cree_par_role         = user_info.get('role', ''),
            departement_id        = departement_id,
            direction_id          = direction_id or '',
            direction_centrale_id = direction_centrale_id or '',

            # ── Parties ───────────────────────────────────────────────
            societe_a_nom = data.get('societe_a_nom') or 'SONATRACH',
            societe_b_nom = data.get('societe_b_nom') or data.get('partie_b_nom') or '',
            pays_partie_b = data.get('pays_partie_b') or 'Algérie',

            # ── Représentants Partie A ────────────────────────────────
            societe_a_representant_nom      = data.get('societe_a_representant_nom'),
            societe_a_representant_prenom   = data.get('societe_a_representant_prenom'),
            societe_a_representant_fonction = data.get('societe_a_representant_fonction'),

            # ── Représentants Partie B ────────────────────────────────
            societe_b_siege_social          = data.get('societe_b_siege_social'),
            societe_b_representant_nom      = data.get('societe_b_representant_nom'),
            societe_b_representant_prenom   = data.get('societe_b_representant_prenom'),
            societe_b_representant_fonction = data.get('societe_b_representant_fonction'),

            # ── Contacts Art. 21 ──────────────────────────────────────
            notification_adresse_ligne1 = data.get('notification_adresse_ligne1'),
            notification_adresse_ligne2 = data.get('notification_adresse_ligne2'),
            fax_fournisseur             = data.get('fax_fournisseur'),
            telephone_fournisseur       = data.get('telephone_fournisseur'),
            email_fournisseur           = data.get('email_fournisseur'),

            # ── Signatures Art. 22 ────────────────────────────────────
            nom_client           = data.get('nom_client'),
            prenom_client        = data.get('prenom_client'),
            fonction_client      = data.get('fonction_client'),
            nom_fournisseur      = data.get('nom_fournisseur'),
            prenom_fournisseur   = data.get('prenom_fournisseur'),
            fonction_fournisseur = data.get('fonction_fournisseur'),

            # ── Détails ───────────────────────────────────────────────
            objet               = data.get('objet') or '',
            date_signature      = data.get('date_signature') or None,
            date_debut          = data.get('date_debut') or None,
            date_fin            = data.get('date_fin') or None,
            delai_livraison_mois = delai_livraison_mois,   # NOUVEAU — déclenche le calcul de date_limite_livraison dans save()
            montant             = data.get('montant') or 0,
            devise              = data.get('devise') or 'DZD',
            conditions_paiement = data.get('conditions_paiement'),

            # ── Document (optionnel) ──────────────────────────────────
            fichier_original = fichier if fichier else None,
            fichier_format   = ext,
            texte_extrait    = '',
            ocr_effectue     = False,
            statut           = data.get('statut') or 'brouillon',
        )

        # ── Métadonnées (pénalités, garantie, caution…) ───────────────
        METADONNEES_FIELDS = [
            'delai_livraison_mois',
            'penalite_retard_pct',
            'penalite_plafond_pct',
            'duree_garantie_mois',
            'caution_bonne_fin_pct',
            'caution_bonne_fin_dzd',
            'tribunal_competent',
            'mode_reglement',
            'avance_demarrage_pct',
        ]
        metadonnees = {}
        for cle in METADONNEES_FIELDS:
            val = data.get(cle)
            if val not in (None, '', [], {}):
                metadonnees[cle] = val

        _save_metadonnees(contrat, metadonnees)

        # ── Analyse des risques ───────────────────────────────────────
        # Construire un parsed équivalent à celui de l'OCR
        parsed_for_risk = {
            'numero_contrat': contrat.numero_contrat,
            'titre':          contrat.titre,
            'partie_b_nom':   contrat.societe_b_nom,
            'objet':          contrat.objet,
            'montant':        float(contrat.montant),
            'date_signature': str(contrat.date_signature) if contrat.date_signature else None,
            'date_debut':     str(contrat.date_debut)     if contrat.date_debut     else None,
            'date_fin':       str(contrat.date_fin)       if contrat.date_fin       else None,
            'metadonnees':    metadonnees,
        }

        # Texte brut synthétique pour les regex du moteur
        # (permet à _analyser_different de trouver les mots-clés)
        texte_synthetique = ' '.join([
            contrat.objet or '',
            contrat.conditions_paiement or '',
            data.get('clauses_specifiques') or '',
        ])

        risques_bruts  = analyser_risques(parsed_for_risk, texte_synthetique)
        risques_sauves = _save_risques(contrat, risques_bruts)

        # ── Rapport ───────────────────────────────────────────────────
        champs_obligatoires_rapport = [
            'numero_contrat', 'titre', 'type_contrat',
            'societe_b_nom', 'pays_partie_b', 'objet',
            'date_signature', 'date_debut', 'date_fin', 'montant',
        ]
        champs_trouves   = [c for c in champs_obligatoires_rapport if data.get(c) or getattr(contrat, c, None)]
        champs_manquants = [c for c in champs_obligatoires_rapport if not data.get(c) and not getattr(contrat, c, None)]

        risques_par_type = {
            TYPE_RETARD:      [r for r in risques_sauves if r['type'] == TYPE_RETARD],
            TYPE_IMPRECISION: [r for r in risques_sauves if r['type'] == TYPE_IMPRECISION],
            TYPE_DIFFERENT:   [r for r in risques_sauves if r['type'] == TYPE_DIFFERENT],
        }

        return Response({
            'success': True,
            'methode': 'formulaire',
            'contrat': {
                'id':                    contrat.id,
                'numero_contrat':        contrat.numero_contrat,
                'titre':                 contrat.titre,
                'type_contrat':          contrat.get_type_contrat_display(),
                'type_contrat_code':     contrat.type_contrat,
                'partie_a_nom':          contrat.societe_a_nom,
                'partie_b_nom':          contrat.societe_b_nom,
                'pays_partie_b':         contrat.pays_partie_b,
                'type_partie':           contrat.type_partie,
                'is_international':      contrat.is_international,
                'montant':               float(contrat.montant),
                'devise':                contrat.devise,
                'date_debut':            contrat.date_debut,
                'date_fin':              contrat.date_fin,
                'delai_livraison_mois':   contrat.delai_livraison_mois,
                'date_limite_livraison':  contrat.date_limite_livraison,       # NOUVEAU
                'jours_restants_livraison': contrat.jours_restants_livraison,  # NOUVEAU
                'est_en_retard':          contrat.est_en_retard, 
                'date_signature':        contrat.date_signature,
                'statut':                contrat.statut,
                'cree_par_id':           contrat.cree_par_id,
                'departement_id':        contrat.departement_id,
                'direction_id':          contrat.direction_id,
                'direction_centrale_id': contrat.direction_centrale_id,
                'date_creation':         contrat.date_creation,
                'fichier_joint':         bool(fichier),
            },
            'saisie': {
                'champs_trouves':   champs_trouves,
                'champs_manquants': champs_manquants,
                'metadonnees':      metadonnees,
            },
            'risques': {
                'total':          len(risques_sauves),
                'par_type': {
                    'retard':      len(risques_par_type[TYPE_RETARD]),
                    'imprecision': len(risques_par_type[TYPE_IMPRECISION]),
                    'different':   len(risques_par_type[TYPE_DIFFERENT]),
                },
                'critique_count': sum(1 for r in risques_sauves if r['severite'] == SEV_CRITIQUE),
                'detail':         risques_sauves,
            },
        }, status=201)

    except Exception as e:
        logger.error(f'[FORMULAIRE] {str(e)}', exc_info=True)
        return Response({'success': False, 'error': str(e)}, status=500)
    

# clm/views.py — Vue GET génération PDF contrat

import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from django.http import HttpResponse


@api_view(['GET'])
@authentication_classes([RemoteJWTAuthentication])
@permission_classes([IsAuthenticated])
def generer_pdf_contrat(request, contrat_id):
    """
    GET /clm/contrats/<contrat_id>/pdf/

    Génère et retourne un PDF rempli avec les données du contrat existant,
    en respectant la structure du template Sonatrach type fourniture.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # ── Auth ──────────────────────────────────────────────────────
        token = request.auth
        if not token:
            return Response({'error': 'Token non fourni'}, status=401)

        user_info = get_user_info_from_auth(token)
        if not user_info:
            return Response({'error': 'Utilisateur non trouvé'}, status=401)

        # ── Récupération contrat ──────────────────────────────────────
        try:
            contrat = Contrat.objects.get(id=contrat_id)
        except Contrat.DoesNotExist:
            return Response({'error': 'Contrat introuvable'}, status=404)

        # Vérification accès (même département)
        if str(contrat.departement_id) != str(user_info.get('departement_id')):
            # Laisser passer direction / admin
            role = user_info.get('role', '')
            if role not in ('directeur', 'admin', 'responsable_direction'):
                return Response({'error': 'Accès non autorisé à ce contrat'}, status=403)

        # ── Métadonnées ───────────────────────────────────────────────
        meta = {}
        for m in contrat.metadonnees.all():
            meta[m.cle] = m.valeur

        # ── Helpers ───────────────────────────────────────────────────
        def val(v, defaut='……………………………………………'):
            """Retourne la valeur ou un placeholder si vide."""
            if v in (None, '', 0, '0'):
                return defaut
            return str(v)

        def val_date(d):
            if not d:
                return '……………………………'
            try:
                from datetime import date as date_type
                if isinstance(d, str):
                    from datetime import datetime
                    d = datetime.strptime(d, '%Y-%m-%d').date()
                return d.strftime('%d/%m/%Y')
            except Exception:
                return str(d)

        def meta_val(cle, defaut='……………………'):
            return val(meta.get(cle), defaut)

        # ── Données remplissage ───────────────────────────────────────
        societe_a       = val(contrat.societe_a_nom, 'SONATRACH')
        societe_b       = val(contrat.societe_b_nom)
        siege_b         = val(contrat.societe_b_siege_social)
        rep_a_nom       = val(contrat.societe_a_representant_nom)
        rep_a_prenom    = val(contrat.societe_a_representant_prenom)
        rep_a_fonction  = val(contrat.societe_a_representant_fonction)
        rep_b_nom       = val(contrat.societe_b_representant_nom)
        rep_b_prenom    = val(contrat.societe_b_representant_prenom)
        rep_b_fonction  = val(contrat.societe_b_representant_fonction)

        objet           = val(contrat.objet, 'Non défini')
        numero          = val(contrat.numero_contrat)
        montant_str     = f"{float(contrat.montant):,.2f} DZD" if contrat.montant else '……………………………'
        devise          = val(contrat.devise, 'DZD')
        date_debut      = val_date(contrat.date_debut)
        date_fin        = val_date(contrat.date_fin)
        date_signature  = val_date(contrat.date_signature)

        delai_mois      = val(contrat.delai_livraison_mois, '……')
        date_limite     = val_date(contrat.date_limite_livraison)
        garantie_mois   = meta_val('duree_garantie_mois', '……')
        caution_pct     = meta_val('caution_bonne_fin_pct', '10')
        caution_dzd     = meta_val('caution_bonne_fin_dzd', '……………………………')
        tribunal        = meta_val('tribunal_competent', 'Laghouat')

        notif_ligne1    = val(contrat.notification_adresse_ligne1)
        notif_ligne2    = val(contrat.notification_adresse_ligne2, '')
        fax             = val(contrat.fax_fournisseur)
        telephone       = val(contrat.telephone_fournisseur)
        email           = val(contrat.email_fournisseur)

        sig_client_nom      = val(contrat.nom_client)
        sig_client_prenom   = val(contrat.prenom_client)
        sig_client_fonction = val(contrat.fonction_client)
        sig_four_nom        = val(contrat.nom_fournisseur)
        sig_four_prenom     = val(contrat.prenom_fournisseur)
        sig_four_fonction   = val(contrat.fonction_fournisseur)

        # Lots depuis objet (ou générique)
        lot1 = objet.split('\n')[0][:80] if '\n' in objet else objet[:80]
        lot2 = objet.split('\n')[1][:80] if '\n' in objet and len(objet.split('\n')) > 1 else '……………………………'

        # ── Construction PDF ──────────────────────────────────────────
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2.5*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
            title=f"Contrat {numero}",
            author=societe_a,
        )

        styles   = getSampleStyleSheet()
        W, H     = A4

        # Styles personnalisés
        style_titre = ParagraphStyle(
            'Titre', parent=styles['Title'],
            fontSize=13, spaceAfter=6, spaceBefore=4,
            textColor=colors.HexColor('#003366'),
            alignment=1,
        )
        style_h1 = ParagraphStyle(
            'H1', parent=styles['Heading1'],
            fontSize=11, spaceAfter=4, spaceBefore=10,
            textColor=colors.HexColor('#003366'),
            borderPad=2,
        )
        style_body = ParagraphStyle(
            'Body', parent=styles['Normal'],
            fontSize=9.5, spaceAfter=4, leading=14,
            fontName='Helvetica',
        )
        style_italic = ParagraphStyle(
            'Italic', parent=style_body,
            fontName='Helvetica-Oblique',
            textColor=colors.HexColor('#555555'),
        )
        style_bold = ParagraphStyle(
            'Bold', parent=style_body,
            fontName='Helvetica-Bold',
        )
        style_center = ParagraphStyle(
            'Center', parent=style_body,
            alignment=1,
        )
        style_footer = ParagraphStyle(
            'Footer', parent=style_body,
            fontSize=8, textColor=colors.grey, alignment=1,
        )

        story = []

        def hr():
            story.append(HRFlowable(width='100%', thickness=0.5,
                                    color=colors.HexColor('#003366'), spaceAfter=6))

        def section(titre):
            story.append(Spacer(1, 8))
            story.append(Paragraph(titre, style_h1))
            hr()

        def corps(*lignes):
            for l in lignes:
                story.append(Paragraph(l, style_body))

        def sp(n=1):
            story.append(Spacer(1, n * 6))

        # ═══════════════════════════════════════════════════════════════
        # EN-TÊTE
        # ═══════════════════════════════════════════════════════════════
        story.append(Paragraph(f'« Fourniture {objet[:60]} »', style_footer))
        hr()
        story.append(Paragraph(
            f'Projet de Contrat N° <b>{numero}</b>', style_titre
        ))
        story.append(Paragraph(
            f'La Fourniture de :<br/>'
            f'Lot n° 01 : <b>{lot1}</b><br/>'
            f'Lot n° 02 : <b>{lot2}</b>',
            style_body
        ))
        sp(2)

        # ═══════════════════════════════════════════════════════════════
        # PARTIES CONTRACTANTES
        # ═══════════════════════════════════════════════════════════════
        story.append(Paragraph('<b>PARTIES CONTRACTANTES</b>', style_titre))
        hr()
        corps(
            f'Entre :',
            f'La Société <b>{societe_a}</b>',
            f'Désignée ci-après par l\'expression <i>« le Client »</i>, et représentée par :',
            f'Monsieur : <b>{rep_a_nom} {rep_a_prenom}</b>, '
            f'Fonction : <b>{rep_a_fonction}</b>,',
            f'Ayant tous pouvoirs à l\'effet du présent Contrat.',
        )
        sp()
        corps(
            'D\'une part, Et :',
            f'La société : <b>{societe_b}</b>',
            f'Dont le Siège Social est au : <b>{siege_b}</b>',
            f'Désignée ci-après par l\'expression <i>« le Fournisseur »</i>, et représentée par :',
            f'Monsieur : <b>{rep_b_nom} {rep_b_prenom}</b>, '
            f'Fonction : <b>{rep_b_fonction}</b>,',
            'Ayant tous pouvoirs à l\'effet du présent Contrat.',
            'D\'autre part.',
        )
        sp()
        story.append(Paragraph('<i>Il a été convenu et arrêté ce qui suit :</i>', style_italic))
        sp(2)

        # ═══════════════════════════════════════════════════════════════
        # PRÉAMBULE
        # ═══════════════════════════════════════════════════════════════
        section('Préambule')
        corps(
            f'Attendu que le Client souhaite acquérir <b>{objet}</b> suivant la liste en annexe 2.',
            f'Le Fournisseur accepte d\'assurer la fourniture conformément aux dispositions du présent Contrat.',
            'Le Fournisseur déclare posséder les moyens humains, financiers et matériels, le personnel '
            'spécialisé et l\'expérience nécessaires pour assurer la fourniture objet du présent Contrat.',
        )
        sp(2)

        # ═══════════════════════════════════════════════════════════════
        # ARTICLE 1
        # ═══════════════════════════════════════════════════════════════
        section('Article 1 : Définitions et Objet du Contrat')
        corps(
            '<b>1.1 Définitions :</b>',
            f'• <b>Client</b> : Désigne {societe_a}.',
            f'• <b>Fournisseur</b> : Désigne la société {societe_b}.',
            f'• <b>Site</b> : Désigne le site de livraison convenu entre les Parties.',
            '<b>1.2 Objet du Contrat :</b>',
            f'Le présent Contrat a pour objet la fourniture de :<br/>'
            f'• Lot 01 : <b>{lot1}</b><br/>'
            f'• Lot 02 : <b>{lot2}</b>',
        )
        sp(2)

        # ═══════════════════════════════════════════════════════════════
        # ARTICLE 2
        # ═══════════════════════════════════════════════════════════════
        section('Article 2 : Documents Contractuels')
        corps(
            'Les documents contractuels régissant le présent Contrat sont :',
            '• Le présent Contrat et ses annexes (Lettre de soumission, Spécifications techniques, '
            'Liste descriptive et valorisée, Déclaration à souscrire)',
            '• Le Dossier d\'Appel d\'Offres (DAO).',
            'En cas de contradiction, l\'ordre de priorité ci-dessus prévaudra.',
        )
        sp(2)

        # ═══════════════════════════════════════════════════════════════
        # ARTICLE 3
        # ═══════════════════════════════════════════════════════════════
        section('Article 3 : Mode de Passation et Textes de Référence')
        corps(
            'Le présent Contrat est passé selon la procédure d\'appel à la concurrence ouvert '
            'conformément à la Décision A-408 (R15) du 12 octobre 2004, portant Directive de '
            'passation des marchés de Sonatrach, dûment amendée par la Décision N°94/DG du 21.05.2008.',
            'Le présent Contrat est régi par la législation et la réglementation algériennes en vigueur.',
        )
        sp(2)

        # ═══════════════════════════════════════════════════════════════
        # ARTICLE 4
        # ═══════════════════════════════════════════════════════════════
        section('Article 4 : Délai de Livraison')
        corps(
            f'La livraison complète de la fourniture interviendra au plus tard dans un délai '
            f'de <b>{delai_mois} mois</b> à compter de la mise en vigueur du contrat.',
            f'Date de début : <b>{date_debut}</b> — Date de fin : <b>{date_fin}</b>',
            f'Date limite de livraison (calculée) : <b>{date_limite}</b>',
            'Le Fournisseur livrera les fournitures conformément aux conditions spécifiées par le Client.',
        )
        sp(2)

        # ═══════════════════════════════════════════════════════════════
        # ARTICLE 5
        # ═══════════════════════════════════════════════════════════════
        section('Article 5 : Pénalités de Retard')
        corps(
            'Dans le cas où le délai de livraison n\'est pas respecté, le Fournisseur devra payer '
            'au Client une pénalité de retard de <b>un pourcent (1%)</b> du montant du Contrat '
            'par semaine de retard.',
            'Le montant global de ces pénalités ne pourra excéder <b>dix pourcent (10%)</b> '
            'du montant global du contrat.',
            'Les pénalités dues seront payées dans un délai de quinze (15) jours à compter de '
            'l\'envoi du décompte adressé par le Client au Fournisseur.',
        )
        sp(2)

        # ═══════════════════════════════════════════════════════════════
        # ARTICLE 6
        # ═══════════════════════════════════════════════════════════════
        section('Article 6 : Inspection, Contrôle et Réceptions')
        corps(
            'Le Client ou son représentant aura le droit d\'inspecter et/ou essayer les fournitures '
            'pour s\'assurer de leur conformité au Contrat, sans coût additionnel pour le Client.',
            '<b>Réception provisoire :</b> prononcée sur le Site après vérification de la conformité '
            'quantitative et qualitative.',
            f'<b>Réception définitive :</b> prononcée à l\'expiration d\'un délai de '
            f'<b>{garantie_mois} mois</b> à compter de la date de réception provisoire.',
        )
        sp(2)

        # ═══════════════════════════════════════════════════════════════
        # ARTICLE 7
        # ═══════════════════════════════════════════════════════════════
        section('Article 7 : Garantie')
        corps(
            'Le Fournisseur garantit que toutes les fournitures livrées sont neuves, n\'ont jamais '
            'été utilisées, sont du modèle en service le plus récent.',
            f'Le Fournisseur garantit les éléments constitutifs de la Fourniture pendant une durée '
            f'de <b>{garantie_mois} mois</b> à compter de la date de la réception provisoire.',
            'En cas de défaillance dans un délai de quinze (15) jours à compter de la demande du Client, '
            'celui-ci sera en droit de procéder lui-même ou par l\'intermédiaire d\'un tiers, '
            'aux frais du Fournisseur.',
        )
        sp(2)

        # ═══════════════════════════════════════════════════════════════
        # ARTICLE 8
        # ═══════════════════════════════════════════════════════════════
        section('Article 8 : Montant Contractuel')
        corps(
            f'Le montant global du présent Contrat s\'élève à la somme de : '
            f'<b>{montant_str}</b> en toutes taxes comprises à l\'exception de la TVA.',
            'Les prix unitaires des fournitures sont fermes et non révisables pendant toute la durée du Contrat.',
        )
        sp(2)

        # ═══════════════════════════════════════════════════════════════
        # ARTICLE 9
        # ═══════════════════════════════════════════════════════════════
        section('Article 9 : Modalités de Paiement')
        corps(
            'Le paiement des factures dûment acceptées s\'effectuera par virement bancaire dans '
            'les trente (30) jours suivant la présentation des documents :',
            '• Factures en six (06) exemplaires dont une originale,',
            '• Procès verbal de réception provisoire signé contradictoirement par les deux Parties.',
        )
        sp(2)

        # ═══════════════════════════════════════════════════════════════
        # ARTICLE 10
        # ═══════════════════════════════════════════════════════════════
        section('Article 10 : Caution Bancaire de Bonne Fin d\'Exécution')
        corps(
            f'Une caution bancaire de bonne fin d\'exécution de <b>{caution_pct}%</b> du montant '
            f'du Contrat soit : <b>{caution_dzd} DZD</b> sera mise en place par le Fournisseur '
            f'dans les trente (30) jours suivant la notification du présent contrat.',
            'Cette caution devra être établie au nom du Client par une banque algérienne de premier '
            'ordre agréée par la Banque d\'Algérie.',
            'Cette caution sera libérée dans un délai d\'un (01) mois à compter de la date de '
            'réception définitive de la Fourniture.',
        )
        sp(2)

        # ═══════════════════════════════════════════════════════════════
        # ARTICLE 11
        # ═══════════════════════════════════════════════════════════════
        section('Article 11 : Domiciliations Bancaires')
        corps(
            'Le Client se libérera des sommes dues par lui au titre du présent Contrat, '
            'au compte du Fournisseur ouvert auprès de sa banque domiciliataire.',
        )
        sp(2)

        # ═══════════════════════════════════════════════════════════════
        # ARTICLE 12
        # ═══════════════════════════════════════════════════════════════
        section('Article 12 : Impôts, Droits et Taxes')
        corps(
            'Tous les impôts, Droits et Taxes frappant l\'activité du Fournisseur, exigibles au '
            'titre du présent Contrat, sont à la charge de ce dernier.',
            'S\'agissant des fournitures exonérées de la TVA, le Client délivrera au Fournisseur '
            'les attestations d\'exonération conformément à l\'arrêté interministériel du '
            '07 Décembre 1991.',
        )
        sp(2)

        # ═══════════════════════════════════════════════════════════════
        # ARTICLES 13–15 (regroupés)
        # ═══════════════════════════════════════════════════════════════
        section('Articles 13–15 : Assurance, Documentation, Emballage')
        corps(
            '<b>Art. 13 – Assurance :</b> L\'assurance de la fourniture est à la charge du '
            'Fournisseur jusqu\'au Site du Client.',
            '<b>Art. 14 – Documentation :</b> Le Fournisseur s\'engage à fournir toute la '
            'documentation technique en langue française.',
            '<b>Art. 15 – Emballage :</b> L\'emballage doit être conforme aux normes '
            'internationales de transport et garantir la protection des fournitures.',
        )
        sp(2)

        # ═══════════════════════════════════════════════════════════════
        # ARTICLE 16
        # ═══════════════════════════════════════════════════════════════
        section('Article 16 : Cession')
        corps(
            'Le Fournisseur ne pourra céder tout ou partie du présent Contrat à un tiers, '
            'sans l\'accord écrit préalable et express du Client.',
        )
        sp(2)

        # ═══════════════════════════════════════════════════════════════
        # ARTICLE 17
        # ═══════════════════════════════════════════════════════════════
        section('Article 17 : Force Majeure')
        corps(
            'On entend par force majeure tout acte ou événement imprévisible, irrésistible '
            'et indépendant de la volonté des Parties.',
            'La Partie qui invoque le cas de force majeure devra adresser une notification '
            'dans les <b>quinze (15) jours</b> à compter de la date de survenance de l\'événement.',
        )
        sp(2)

        # ═══════════════════════════════════════════════════════════════
        # ARTICLE 18
        # ═══════════════════════════════════════════════════════════════
        section('Article 18 : Résiliation')
        corps(
            'Le Client peut résilier le Contrat si le Fournisseur est déclaré en faillite '
            'ou devient insolvable, sans indemnisation.',
            'Le Client se réserve le droit de résilier si le Fournisseur a failli à ses '
            'obligations et ne remédie pas dans un délai de <b>dix (10) jours</b> après '
            'mise en demeure écrite.',
        )
        sp(2)

        # ═══════════════════════════════════════════════════════════════
        # ARTICLE 19
        # ═══════════════════════════════════════════════════════════════
        section('Article 19 : Règlement des Différends')
        corps(
            f'Tout différend ayant trait à l\'interprétation et/ou à l\'exécution du Contrat, '
            f'et qui n\'aurait pu être réglé à l\'amiable sera définitivement tranché par le '
            f'tribunal territorialement compétent de <b>{tribunal}</b>.',
        )
        sp(2)

        # ═══════════════════════════════════════════════════════════════
        # ARTICLE 20
        # ═══════════════════════════════════════════════════════════════
        section('Article 20 : Dispositions Générales')
        corps(
            'Le présent Contrat est rédigé en langue française en dix (10) originaux dont '
            'deux (02) conservés par le Fournisseur et huit (08) par le Client.',
        )
        sp(2)

        # ═══════════════════════════════════════════════════════════════
        # ARTICLE 21
        # ═══════════════════════════════════════════════════════════════
        section('Article 21 : Notifications')
        corps('Toute notification doit être effectuée par courrier recommandé avec accusé de réception aux adresses suivantes :')
        sp()

        notif_data = [
            ['', 'Pour le Client', 'Pour le Fournisseur'],
            ['Adresse', societe_a, notif_ligne1],
            ['', '', notif_ligne2],
            ['Fax', '……………………………', fax],
            ['Téléphone', '……………………………', telephone],
            ['Email', '……………………………', email],
        ]
        notif_table = Table(notif_data, colWidths=[3*cm, 7*cm, 7*cm])
        notif_table.setStyle(TableStyle([
            ('BACKGROUND',  (0, 0), (-1, 0), colors.HexColor('#003366')),
            ('TEXTCOLOR',   (0, 0), (-1, 0), colors.white),
            ('FONTNAME',    (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',    (0, 0), (-1, -1), 9),
            ('GRID',        (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('ALIGN',       (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING',     (0, 0), (-1, -1), 5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F8FF')]),
        ]))
        story.append(notif_table)
        sp(2)

        # ═══════════════════════════════════════════════════════════════
        # ARTICLE 22 — SIGNATURES
        # ═══════════════════════════════════════════════════════════════
        section(f'Article 22 : Entrée en Vigueur du Contrat — Fait le {date_signature}')
        corps(
            'Le présent Contrat entrera en vigueur dès :',
            '1. Signature du contrat par les deux Parties ;',
            '2. Notification par le Client au Fournisseur.',
        )
        sp(2)

        sig_data = [
            ['Pour le Client', 'Pour le Fournisseur'],
            [f'Nom : {sig_client_nom}',       f'Nom : {sig_four_nom}'],
            [f'Prénom : {sig_client_prenom}',  f'Prénom : {sig_four_prenom}'],
            [f'Fonction : {sig_client_fonction}', f'Fonction : {sig_four_fonction}'],
            ['\n\n_______________________', '\n\n_______________________'],
            ['(Signature et Cachet)', '(Signature et Cachet)'],
        ]
        sig_table = Table(sig_data, colWidths=[8.5*cm, 8.5*cm])
        sig_table.setStyle(TableStyle([
            ('BACKGROUND',  (0, 0), (-1, 0), colors.HexColor('#003366')),
            ('TEXTCOLOR',   (0, 0), (-1, 0), colors.white),
            ('FONTNAME',    (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',    (0, 0), (-1, -1), 9.5),
            ('GRID',        (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('ALIGN',       (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING',     (0, 0), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F8FF')]),
        ]))
        story.append(sig_table)
        sp()

        # ── Pied de page ──────────────────────────────────────────────
        hr()
        story.append(Paragraph(
            f'« Fourniture {objet[:60]} » — Contrat N° {numero} — Généré le '
            f'{__import__("datetime").date.today().strftime("%d/%m/%Y")}',
            style_footer,
        ))

        # ── Build ─────────────────────────────────────────────────────
        doc.build(story)
        buffer.seek(0)

        filename = f"Contrat_{numero.replace('/', '-')}.pdf"
        response = HttpResponse(buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['X-Contrat-Id']        = str(contrat.id)
        response['X-Contrat-Numero']    = numero

        logger.info(f'[PDF] Généré : {filename} pour contrat {contrat.id}')
        return response

    except Exception as e:
        logger.error(f'[PDF] {str(e)}', exc_info=True)
        return Response({'success': False, 'error': str(e)}, status=500)
    
# clm/views.py — ajout

@api_view(['GET'])
@authentication_classes([RemoteJWTAuthentication])
@permission_classes([IsResponsableDepartement])
def list_risques_contrat(request, contrat_id):
    """
    GET /clm/contrats/<id>/risques/
    
    Retourne tous les risques détectés sur un contrat,
    groupés par type (retard / imprecision / different).
    """
    try:
        token     = request.auth
        user_info = get_user_info_from_auth(token)
        if not user_info:
            return Response({'error': 'Non authentifié'}, status=401)

        try:
            contrat = Contrat.objects.get(id=contrat_id)
        except Contrat.DoesNotExist:
            return Response({'error': 'Contrat non trouvé'}, status=404)

        risques_qs = RisqueContrat.objects.filter(contrat=contrat).order_by('type_risque', '-severite')

        def fmt(r):
            return {
                'id':               r.id,
                'code':             r.code,
                'type':             r.type_risque,
                'description':      r.description,
                'severite':         r.severite,
                'article_ref':      r.article_ref,
                'suggestion':       r.suggestion,
                'occurrence_count': r.occurrence_count,
                'niveau_alerte':    r.niveau_alerte,
                'resolu':           r.resolu,
                'date_detection':   r.date_detection,
            }

        return Response({
            'contrat_id':     contrat_id,
            'numero_contrat': contrat.numero_contrat,
            'total':          risques_qs.count(),
            'retard':         [fmt(r) for r in risques_qs.filter(type_risque='retard')],
            'imprecision':    [fmt(r) for r in risques_qs.filter(type_risque='imprecision')],
            'different':      [fmt(r) for r in risques_qs.filter(type_risque='different')],
        })

    except Exception as e:
        return Response({'error': str(e)}, status=500)



# clm/views.py — Ajouter ces deux vues
import logging

logger = logging.getLogger(__name__)
@api_view(['GET'])
@authentication_classes([RemoteJWTAuthentication])
@permission_classes([IsAuthenticated])
def list_contrats(request):
    """
    GET /clm/contrats/

    Retourne la liste des contrats accessibles selon le rôle du user.

    Règles d'accès :
      - chef_departement       → seulement son département
      - directeur_direction    → tous les contrats de sa direction
      - directeur_centrale     → tous les contrats de sa direction centrale
      - admin / juridique      → tous les contrats

    Query params :
      ?statut=actif|brouillon|expire|resilie
      ?type_contrat=fourniture|service|travaux|partenariat|vente|transfert
      ?type_partie=nationale|etrangere
      ?is_international=true|false
      ?search=mot_cle          → cherche dans numero, titre, societe_b_nom, objet
      ?ordering=date_creation|-date_creation|montant|-montant
      ?limit=20&offset=0
    """
    try:
        token     = request.auth
        user_info = get_user_info_from_auth(token)
        if not user_info:
            return Response({'error': 'Non authentifié'}, status=401)

        role          = user_info.get('role', '')
        departement_id = str(user_info.get('departement_id', ''))
        direction_id   = str(user_info.get('direction_id', ''))
        direction_centrale_id = str(user_info.get('direction_centrale_id', ''))

        # ── Filtre de base selon le rôle ──────────────────────────────
        qs = Contrat.objects.all()

        if role in ('admin', 'juridique'):
            pass  # accès total
        elif role == 'directeur_centrale':
            qs = qs.filter(direction_centrale_id=direction_centrale_id)
        elif role == 'directeur_direction':
            qs = qs.filter(direction_id=direction_id)
        else:
            # chef_departement et tout autre rôle → son département uniquement
            qs = qs.filter(departement_id=departement_id)

        # ── Filtres query params ──────────────────────────────────────
        statut = request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)

        type_contrat = request.query_params.get('type_contrat')
        if type_contrat:
            qs = qs.filter(type_contrat=type_contrat)

        type_partie = request.query_params.get('type_partie')
        if type_partie:
            qs = qs.filter(type_partie=type_partie)

        is_intl = request.query_params.get('is_international')
        if is_intl is not None:
            qs = qs.filter(is_international=(is_intl.lower() == 'true'))

        search = request.query_params.get('search', '').strip()
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(numero_contrat__icontains=search) |
                Q(titre__icontains=search)           |
                Q(societe_b_nom__icontains=search)   |
                Q(objet__icontains=search)
            )

        # ── Tri ───────────────────────────────────────────────────────
        ordering_map = {
            'date_creation':  'date_creation',
            '-date_creation': '-date_creation',
            'montant':        'montant',
            '-montant':       '-montant',
            'date_fin':       'date_fin',
            '-date_fin':      '-date_fin',
        }
        ordering = request.query_params.get('ordering', '-date_creation')
        qs = qs.order_by(ordering_map.get(ordering, '-date_creation'))

        # ── Pagination ────────────────────────────────────────────────
        total  = qs.count()
        limit  = min(int(request.query_params.get('limit',  20)), 100)
        offset = int(request.query_params.get('offset', 0))
        qs     = qs[offset: offset + limit]

        # ── Sérialisation ─────────────────────────────────────────────
        def fmt(c):
            return {
                'id':                    c.id,
                'numero_contrat':        c.numero_contrat,
                'titre':                 c.titre,
                'type_contrat':          c.get_type_contrat_display(),
                'type_contrat_code':     c.type_contrat,
                'statut':                c.statut,
                'partie_a_nom':          c.societe_a_nom,
                'partie_b_nom':          c.societe_b_nom,
                'pays_partie_b':         c.pays_partie_b,
                'type_partie':           c.type_partie,
                'is_international':      c.is_international,
                'montant':               float(c.montant),
                'devise':                c.devise,
                'date_signature':        c.date_signature,
                'date_debut':            c.date_debut,
                'date_fin':              c.date_fin,
                'delai_livraison_mois':    c.delai_livraison_mois,     # NOUVEAU
                'date_limite_livraison':   c.date_limite_livraison,    # NOUVEAU
                'est_en_retard':           c.est_en_retard,            # NOUVEAU
                'departement_id':        c.departement_id,
                'direction_id':          c.direction_id,
                'direction_centrale_id': c.direction_centrale_id,
                'date_creation':         c.date_creation,
                'date_modification':     c.date_modification,
                'risques_total':    c.risques.count(),
                'risques_critiques': c.risques.filter(severite='critique', resolu=False).count(),
                'risques_non_resolus': c.risques.filter(resolu=False).count(),
            }

        return Response({
            'success': True,
            'total':   total,
            'limit':   limit,
            'offset':  offset,
            'results': [fmt(c) for c in qs],
        })

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'[LIST CONTRATS] {e}', exc_info=True)
        return Response({'success': False, 'error': str(e)}, status=500)


# @api_view(['GET'])
# @authentication_classes([RemoteJWTAuthentication])
# @permission_classes([IsAuthenticated])
# def detail_contrat(request, contrat_id):
#     """
#     GET /clm/contrats/<id>/

#     Retourne toutes les données d'un contrat :
#       - Champs principaux
#       - Métadonnées (pénalités, garantie, caution…)
#       - Risques (groupés par type + résumé escalade)
#       - Notifications non traitées
#       - Décisions d'escalade
#     """
#     try:
#         token     = request.auth
#         user_info = get_user_info_from_auth(token)
#         if not user_info:
#             return Response({'error': 'Non authentifié'}, status=401)

#         role           = user_info.get('role', '')
#         departement_id = str(user_info.get('departement_id', ''))
#         direction_id   = str(user_info.get('direction_id', ''))
#         direction_centrale_id = str(user_info.get('direction_centrale_id', ''))

#         try:
#             contrat = Contrat.objects.prefetch_related(
#                 'metadonnees', 'risques', 'notifications', 'decisions_escalade'
#             ).get(id=contrat_id)
#         except Contrat.DoesNotExist:
#             return Response({'error': 'Contrat introuvable'}, status=404)

#         # ── Contrôle d'accès ──────────────────────────────────────────
#         acces = (
#             role in ('admin', 'juridique') or
#             (role == 'directeur_centrale' and str(contrat.direction_centrale_id) == direction_centrale_id) or
#             (role == 'directeur_direction' and str(contrat.direction_id) == direction_id) or
#             str(contrat.departement_id) == departement_id
#         )
#         if not acces:
#             return Response({'error': 'Accès non autorisé à ce contrat'}, status=403)

#         # ── Métadonnées ───────────────────────────────────────────────
#         metadonnees = {m.cle: m.valeur for m in contrat.metadonnees.all()}

#         # ── Risques ───────────────────────────────────────────────────
#         def fmt_risque(r):
#             return {
#                 'id':               r.id,
#                 'code':             r.code,
#                 'type':             r.type_risque,
#                 'description':      r.description,
#                 'severite':         r.severite,
#                 'article_ref':      r.article_ref,
#                 'suggestion':       r.suggestion,
#                 'occurrence_count': r.occurrence_count,
#                 'niveau_alerte':    r.niveau_alerte,
#                 'resolu':           r.resolu,
#                 'date_detection':   r.date_detection,
#                 'date_resolution':  r.date_resolution,
#             }

#         tous_risques   = contrat.risques.all()
#         risques_actifs = tous_risques.filter(resolu=False)

#         risques_data = {
#             'total':          tous_risques.count(),
#             'non_resolus':    risques_actifs.count(),
#             'critiques':      risques_actifs.filter(severite='critique').count(),
#             'retard':         [fmt_risque(r) for r in risques_actifs.filter(type_risque='retard')],
#             'imprecision':    [fmt_risque(r) for r in risques_actifs.filter(type_risque='imprecision')],
#             'different':      [fmt_risque(r) for r in risques_actifs.filter(type_risque='different')],
#             'resolus':        [fmt_risque(r) for r in tous_risques.filter(resolu=True)],
#         }

#         # ── Escalade (rapport léger) ──────────────────────────────────
#         try:
#             from .escalade_engine import rapport_escalade
#             risques_pour_rapport = [
#                 {
#                     'id':              r.id,
#                     'code':            r.code,
#                     'type':            r.type_risque,
#                     'severite':        r.severite,
#                     'occurrence_count': r.occurrence_count,
#                 }
#                 for r in risques_actifs
#             ]
#             escalade_data = rapport_escalade(contrat, risques_pour_rapport)
#         except Exception:
#             escalade_data = {}

#         # ── Notifications non traitées ────────────────────────────────
#         notifs = contrat.notifications.filter(traitee=False).order_by('-date_creation')[:10]
#         notifs_data = [
#             {
#                 'id':              n.id,
#                 'niveau':          n.niveau,
#                 'type_notif':      n.type_notif,
#                 'titre':           n.titre,
#                 'lue':             n.lue,
#                 'destinataire_role': n.destinataire_role,
#                 'date_creation':   n.date_creation,
#             }
#             for n in notifs
#         ]

#         # ── Décisions ─────────────────────────────────────────────────
#         decisions = list(
#             contrat.decisions_escalade.values(
#                 'id', 'decideur_role', 'decision', 'commentaire', 'date_decision'
#             ).order_by('-date_decision')
#         )

#         return Response({
#             'success': True,
#             'contrat': {
#                 # Identification
#                 'id':                    contrat.id,
#                 'numero_contrat':        contrat.numero_contrat,
#                 'titre':                 contrat.titre,
#                 'type_contrat':          contrat.get_type_contrat_display(),
#                 'type_contrat_code':     contrat.type_contrat,
#                 'statut':                contrat.statut,
#                 'objet':                 contrat.objet,

#                 # Parties
#                 'partie_a_nom':          contrat.societe_a_nom,
#                 'partie_b_nom':          contrat.societe_b_nom,
#                 'pays_partie_b':         contrat.pays_partie_b,
#                 'type_partie':           contrat.type_partie,
#                 'is_international':      contrat.is_international,
#                 'societe_b_siege_social': contrat.societe_b_siege_social,

#                 # Représentants Partie A
#                 'rep_a_nom':      contrat.societe_a_representant_nom,
#                 'rep_a_prenom':   contrat.societe_a_representant_prenom,
#                 'rep_a_fonction': contrat.societe_a_representant_fonction,

#                 # Représentants Partie B
#                 'rep_b_nom':      contrat.societe_b_representant_nom,
#                 'rep_b_prenom':   contrat.societe_b_representant_prenom,
#                 'rep_b_fonction': contrat.societe_b_representant_fonction,

#                 # Contacts Art. 21
#                 'notification_adresse_ligne1': contrat.notification_adresse_ligne1,
#                 'notification_adresse_ligne2': contrat.notification_adresse_ligne2,
#                 'fax_fournisseur':             contrat.fax_fournisseur,
#                 'telephone_fournisseur':       contrat.telephone_fournisseur,
#                 'email_fournisseur':           contrat.email_fournisseur,

#                 # Signatures Art. 22
#                 'nom_client':        contrat.nom_client,
#                 'prenom_client':     contrat.prenom_client,
#                 'fonction_client':   contrat.fonction_client,
#                 'nom_fournisseur':   contrat.nom_fournisseur,
#                 'prenom_fournisseur': contrat.prenom_fournisseur,
#                 'fonction_fournisseur': contrat.fonction_fournisseur,

#                 # Financier
#                 'montant':               float(contrat.montant),
#                 'devise':                contrat.devise,
#                 'conditions_paiement':   contrat.conditions_paiement,

#                 # Dates
#                 'date_signature':    contrat.date_signature,
#                 'date_debut':        contrat.date_debut,
#                 'date_fin':          contrat.date_fin,
#                 'date_creation':     contrat.date_creation,
#                 'date_modification': contrat.date_modification,

#                 # Organisation
#                 'cree_par_id':           contrat.cree_par_id,
#                 'cree_par_role':         contrat.cree_par_role,
#                 'departement_id':        contrat.departement_id,
#                 'direction_id':          contrat.direction_id,
#                 'direction_centrale_id': contrat.direction_centrale_id,

#                 # Document
#                 'ocr_effectue':  contrat.ocr_effectue,
#                 'fichier_format': contrat.fichier_format,
#                 'moteur_ocr':    contrat.moteur_ocr,
#                 'pdf_url':       contrat.pdf_url,
#             },
#             'metadonnees': metadonnees,
#             'risques':     risques_data,
#             'escalade':    escalade_data,
#             'notifications_en_attente': notifs_data,
#             'decisions':   decisions,
#         })

#     except Exception as e:
#         import logging
#         logging.getLogger(__name__).error(f'[DETAIL CONTRAT] {e}', exc_info=True)
#         return Response({'success': False, 'error': str(e)}, status=500)
@api_view(['GET'])
@authentication_classes([RemoteJWTAuthentication])
@permission_classes([IsAuthenticated])
def detail_contrat(request, contrat_id):
    """
    GET /clm/contrats/<id>/
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        token     = request.auth
        user_info = get_user_info_from_auth(token)
        if not user_info:
            return Response({'error': 'Non authentifié'}, status=401)

        role                  = user_info.get('role', '')
        departement_id        = str(user_info.get('departement_id', ''))
        direction_id          = str(user_info.get('direction_id', ''))
        direction_centrale_id = str(user_info.get('direction_centrale_id', ''))

        # ── Récupération contrat ──────────────────────────────────────
        try:
            contrat = Contrat.objects.prefetch_related(
                'metadonnees', 'risques'
            ).get(id=contrat_id)
        except Contrat.DoesNotExist:
            return Response({'error': 'Contrat introuvable'}, status=404)

        # ── Contrôle d'accès ──────────────────────────────────────────
        acces = (
            role in ('admin', 'juridique') or
            (role == 'directeur_centrale'  and str(contrat.direction_centrale_id) == direction_centrale_id) or
            (role == 'directeur_direction' and str(contrat.direction_id) == direction_id) or
            str(contrat.departement_id) == departement_id
        )
        if not acces:
            return Response({'error': 'Accès non autorisé à ce contrat'}, status=403)

        # ── Métadonnées ───────────────────────────────────────────────
        metadonnees = {m.cle: m.valeur for m in contrat.metadonnees.all()}

        # ── Risques ───────────────────────────────────────────────────
        def fmt_risque(r):
            return {
                'id':               r.id,
                'code':             r.code,
                'type':             r.type_risque,
                'description':      r.description,
                'severite':         r.severite,
                'article_ref':      r.article_ref,
                'suggestion':       r.suggestion,
                'occurrence_count': r.occurrence_count,
                'niveau_alerte':    r.niveau_alerte,
                'resolu':           r.resolu,
                'date_detection':   r.date_detection,
                'date_resolution':  r.date_resolution,
            }

        tous_risques   = contrat.risques.all()
        risques_actifs = tous_risques.filter(resolu=False)

        risques_data = {
            'total':       tous_risques.count(),
            'non_resolus': risques_actifs.count(),
            'critiques':   risques_actifs.filter(severite='critique').count(),
            'retard':      [fmt_risque(r) for r in risques_actifs.filter(type_risque='retard')],
            'imprecision': [fmt_risque(r) for r in risques_actifs.filter(type_risque='imprecision')],
            'different':   [fmt_risque(r) for r in risques_actifs.filter(type_risque='different')],
            'resolus':     [fmt_risque(r) for r in tous_risques.filter(resolu=True)],
        }

        # ── Escalade (rapport léger) ──────────────────────────────────
        try:
            from .escalade_engine import rapport_escalade
            risques_pour_rapport = [
                {
                    'id':               r.id,
                    'code':             r.code,
                    'type':             r.type_risque,
                    'severite':         r.severite,
                    'occurrence_count': r.occurrence_count,
                }
                for r in risques_actifs
            ]
            escalade_data = rapport_escalade(contrat, risques_pour_rapport)
        except Exception as e_esc:
            logger.warning(f'[DETAIL CONTRAT] escalade_engine non disponible : {e_esc}')
            escalade_data = {}

        # ── Notifications non traitées (optionnel si modèle pas migré) ─
        try:
            from .models_escalade import NotificationEscalade, DecisionEscalade
            notifs = NotificationEscalade.objects.filter(
                contrat=contrat, traitee=False
            ).order_by('-date_creation')[:10]
            notifs_data = [
                {
                    'id':               n.id,
                    'niveau':           n.niveau,
                    'type_notif':       n.type_notif,
                    'titre':            n.titre,
                    'lue':              n.lue,
                    'destinataire_role': n.destinataire_role,
                    'date_creation':    n.date_creation,
                }
                for n in notifs
            ]
            decisions = list(
                DecisionEscalade.objects.filter(contrat=contrat).values(
                    'id', 'decideur_role', 'decision', 'commentaire', 'date_decision'
                ).order_by('-date_decision')
            )
        except Exception as e_notif:
            logger.warning(f'[DETAIL CONTRAT] models_escalade non disponible : {e_notif}')
            notifs_data = []
            decisions   = []

        return Response({
            'success': True,
            'contrat': {
                # Identification
                'id':                contrat.id,
                'numero_contrat':    contrat.numero_contrat,
                'titre':             contrat.titre,
                'type_contrat':      contrat.get_type_contrat_display(),
                'type_contrat_code': contrat.type_contrat,
                'statut':            contrat.statut,
                'objet':             contrat.objet,

                # Parties
                'partie_a_nom':           contrat.societe_a_nom,
                'partie_b_nom':           contrat.societe_b_nom,
                'pays_partie_b':          contrat.pays_partie_b,
                'type_partie':            contrat.type_partie,
                'is_international':       contrat.is_international,
                'societe_b_siege_social': contrat.societe_b_siege_social,

                # Représentants Partie A
                'rep_a_nom':      contrat.societe_a_representant_nom,
                'rep_a_prenom':   contrat.societe_a_representant_prenom,
                'rep_a_fonction': contrat.societe_a_representant_fonction,

                # Représentants Partie B
                'rep_b_nom':      contrat.societe_b_representant_nom,
                'rep_b_prenom':   contrat.societe_b_representant_prenom,
                'rep_b_fonction': contrat.societe_b_representant_fonction,

                # Contacts Art. 21
                'notification_adresse_ligne1': contrat.notification_adresse_ligne1,
                'notification_adresse_ligne2': contrat.notification_adresse_ligne2,
                'fax_fournisseur':             contrat.fax_fournisseur,
                'telephone_fournisseur':       contrat.telephone_fournisseur,
                'email_fournisseur':           contrat.email_fournisseur,

                # Signatures Art. 22
                'nom_client':          contrat.nom_client,
                'prenom_client':       contrat.prenom_client,
                'fonction_client':     contrat.fonction_client,
                'nom_fournisseur':     contrat.nom_fournisseur,
                'prenom_fournisseur':  contrat.prenom_fournisseur,
                'fonction_fournisseur': contrat.fonction_fournisseur,

                # Financier
                'montant':             float(contrat.montant),
                'devise':              contrat.devise,
                'conditions_paiement': contrat.conditions_paiement,

                # Dates
                'date_signature':    contrat.date_signature,
                'date_debut':        contrat.date_debut,
                'date_fin':          contrat.date_fin,
                'date_creation':     contrat.date_creation,
                'date_modification': contrat.date_modification,

                 # Délai & date limite de livraison — NOUVEAU
                'delai_livraison_mois':     contrat.delai_livraison_mois,
                'date_limite_livraison':    contrat.date_limite_livraison,
                'jours_restants_livraison': contrat.jours_restants_livraison,
                'est_en_retard':            contrat.est_en_retard,

                # Organisation
                'cree_par_id':           contrat.cree_par_id,
                'cree_par_role':         contrat.cree_par_role,
                'departement_id':        contrat.departement_id,
                'direction_id':          contrat.direction_id,
                'direction_centrale_id': contrat.direction_centrale_id,

                # Document
                'ocr_effectue':  contrat.ocr_effectue,
                'fichier_format': contrat.fichier_format,
                'moteur_ocr':    contrat.moteur_ocr,
                'pdf_url':       contrat.pdf_url,
            },
            'metadonnees':              metadonnees,
            'risques':                  risques_data,
            'escalade':                 escalade_data,
            'notifications_en_attente': notifs_data,
            'decisions':                decisions,
        })

    except Exception as e:
        logger.error(f'[DETAIL CONTRAT] {e}', exc_info=True)
        return Response({'success': False, 'error': str(e)}, status=500)
"""
clm/views.py  — CORRIGÉ

Problème d'origine :
  GET /clm/contrats/{id}/alertes/ appelait le gateway sur /clm/...
  → le gateway routait vers Django (Port 8012) au lieu du service Notification
  → Django validait le JWT avec IsAuthenticated → token_not_valid

Corrections :
  1. get_alertes_contrat() appelle notification_client.get_alertes_retard()
     qui utilise NOTIFICATION_SERVICE_URL + /notifications/risk-alerts/
     (route gateway correcte → Node.js Notification)
  2. Le JWT est propagé tel quel depuis le header Authorization
  3. analyser_contrat() inchangé fonctionnellement, léger nettoyage
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .risk_engine import analyser_risques, get_niveau_escalade
from .notification_client import envoyer_alertes_risque, get_alertes_retard   # ← import groupé ici
from .models import Contrat
from .contract_parser import parse_contract_data

# ══════════════════════════════════════════════════════════════
# POST /clm/contrats/{id}/analyser/
# ══════════════════════════════════════════════════════════════
# @api_view(['POST'])
# @authentication_classes([RemoteJWTAuthentication])      # ✅ MÊME auth que toutes les autres views
# @permission_classes([IsResponsableDepartement])          # ✅ MÊME permission que toutes les autres views
# def analyser_contrat(request, contrat_id):
#     """
#     1. Charge le contrat
#     2. Parse les données + texte brut
#     3. Analyse les risques
#     4. Envoie les alertes retard au service Notification
#     5. Retourne tous les risques + résultat notification
#     """
#     token = request.auth   # ✅ RemoteJWTAuthentication stocke le token brut dans request.auth
#     if not token:
#         return Response({'error': 'Token non fourni'}, status=401)

#     try:
#         contrat = Contrat.objects.get(pk=contrat_id)
#     except Contrat.DoesNotExist:
#         return Response({'error': 'Contrat non trouvé'}, status=404)

#     # Parse + analyse
#     parsed  = parse_contract_data(contrat)
#     texte   = getattr(contrat, 'texte_extrait', '') or getattr(contrat, 'texte_brut', '') or ''
#     risques = analyser_risques(parsed, texte)

#     # Enrichir les risques retard avec le niveau d'escalade
#     for r in risques:
#         r.setdefault('occurrence_count', 1)
#         if r.get('type') == 'retard':
#             r['escalade'] = get_niveau_escalade(r['occurrence_count'])

#     # Envoyer au service Notification via /notifications/risk-alerts/
#     notif_result = envoyer_alertes_risque(contrat_id, risques, token)

#     return Response({
#         'contrat_id':   contrat_id,
#         'risques':      risques,
#         'notification': notif_result,
#     })


# ══════════════════════════════════════════════════════════════
# PROBLÈME
# ══════════════════════════════════════════════════════════════
#
# views.py re-parse le texte brut à chaque appel de /analyser/
# → parsed peut manquer date_debut / delai_livraison_mois
# → _analyser_retard ne génère pas R-07
# → envoyer_alertes_risque reçoit une liste vide de risques retard
# → sent_count = 0
#
# SOLUTION : lire les risques déjà sauvegardés en base Django
# (RisqueContrat ou le modèle équivalent) au lieu de re-analyser.
# ══════════════════════════════════════════════════════════════


# ──────────────────────────────────────────────────────────────
# OPTION A — Recommandée
# Lire les risques retard depuis la base Django et les envoyer
# ──────────────────────────────────────────────────────────────

@api_view(['POST'])
@authentication_classes([RemoteJWTAuthentication])
@permission_classes([IsResponsableDepartement])
def analyser_contrat(request, contrat_id):
    token = request.auth
    if not token:
        return Response({'error': 'Token non fourni'}, status=401)

    try:
        contrat = Contrat.objects.get(pk=contrat_id)
    except Contrat.DoesNotExist:
        return Response({'error': 'Contrat non trouvé'}, status=404)

    # ✅ Re-analyse complète depuis le texte brut
    texte  = getattr(contrat, 'texte_extrait', '') or getattr(contrat, 'texte_brut', '') or ''
    parsed = parse_contract_data(texte)
    risques_analyses = analyser_risques(parsed, texte)

    # ✅ Sauvegarder/mettre à jour les risques en base Django
    # (votre logique existante de sauvegarde ici)

    # ✅ Lire UNIQUEMENT les risques retard depuis la base Django
    #    (ceux qui ont déjà un id, occurrence_count, etc.)
    risques_retard_bdd = RisqueContrat.objects.filter(
        contrat_id=contrat_id,
        type='retard',
        resolu=False,
    )

    # Construire la liste à envoyer au service Notification
    risques_a_notifier = []
    for r in risques_retard_bdd:
        risques_a_notifier.append({
            'code':            r.code,
            'type':            r.type,
            'description':     r.description,
            'severite':        r.severite,
            'article_ref':     r.article_ref or '',
            'suggestion':      r.suggestion or '',
            'occurrence_count': r.occurrence_count,
            'escalade':        get_niveau_escalade(r.occurrence_count),
        })

    # ✅ Envoyer uniquement les retards au service Notification
    notif_result = envoyer_alertes_risque(contrat_id, risques_a_notifier, token)

    return Response({
        'contrat_id':   contrat_id,
        'risques':      risques_analyses,   # tous les risques pour l'affichage
        'notification': notif_result,       # résultat envoi retards uniquement
    })


# ──────────────────────────────────────────────────────────────
# OPTION B — Si vous n'avez pas de modèle Django RisqueContrat
# Filtrer les risques analysés par type == 'retard'
# ──────────────────────────────────────────────────────────────

# @api_view(['POST'])
# @authentication_classes([RemoteJWTAuthentication])
# @permission_classes([IsResponsableDepartement])
# def analyser_contrat(request, contrat_id):
#     token = request.auth
#     if not token:
#         return Response({'error': 'Token non fourni'}, status=401)

#     try:
#         contrat = Contrat.objects.get(pk=contrat_id)
#     except Contrat.DoesNotExist:
#         return Response({'error': 'Contrat non trouvé'}, status=404)

#     # ✅ parse_contract_data doit recevoir l'OBJET contrat, pas le texte brut
#     #    (pour avoir accès à date_debut, delai_livraison_mois, etc.)
#     texte  = getattr(contrat, 'texte_extrait', '') or getattr(contrat, 'texte_brut', '') or ''
#     parsed = parse_contract_data(contrat.texte_extrait or "")
#     risques = analyser_risques(parsed, texte)

#     # Enrichir tous les risques
#     for r in risques:
#         r.setdefault('occurrence_count', 1)
#         r['escalade'] = get_niveau_escalade(r['occurrence_count'])

#     # ✅ Envoyer UNIQUEMENT les risques retard au service Notification
#     risques_retard = [r for r in risques if r.get('type') == 'retard']
#     notif_result = envoyer_alertes_risque(contrat_id, risques_retard, token)

#     return Response({
#         'contrat_id':   contrat_id,
#         'risques':      risques,        # tous les risques pour l'affichage
#         'notification': notif_result,   # résultat envoi retards uniquement
#     })
# d
# @api_view(['POST'])
# @authentication_classes([RemoteJWTAuthentication])
# @permission_classes([IsResponsableDepartement])
# def analyser_contrat(request, contrat_id):
#     token = request.auth
#     if not token:
#         return Response({'error': 'Token non fourni'}, status=401)

#     try:
#         contrat = Contrat.objects.prefetch_related('metadonnees', 'risques').get(pk=contrat_id)
#     except Contrat.DoesNotExist:
#         return Response({'error': 'Contrat non trouvé'}, status=404)

#     texte = contrat.texte_extrait or ''
    
#     # Métadonnées depuis la BDD
#     metadonnees_dict = {m.cle: m.valeur for m in contrat.metadonnees.all()}

#     # ✅ parsed construit depuis l'objet Django — date_debut vient du champ Django
#     parsed = {
#         'montant':              float(contrat.montant),
#         'objet':                contrat.objet,
#         'date_debut':           str(contrat.date_debut) if contrat.date_debut else None,  # ← FIX
#         'date_fin':             str(contrat.date_fin)   if contrat.date_fin   else None,
#         'date_signature':       str(contrat.date_signature) if contrat.date_signature else None,
#         'nom_fournisseur':      contrat.nom_fournisseur,
#         'fonction_fournisseur': contrat.fonction_fournisseur,
#         'societe_b_representant_nom':      contrat.societe_b_representant_nom,
#         'societe_b_representant_fonction': contrat.societe_b_representant_fonction,
#         'metadonnees':          metadonnees_dict,
#     }

#     risques_bruts = analyser_risques(parsed, texte)
#     risques_sauves = _save_risques(contrat, risques_bruts)

#     for r in risques_sauves:
#         r['escalade'] = get_niveau_escalade(r.get('occurrence_count', 1))

#     # Envoyer uniquement les retards
#     risques_retard = [r for r in risques_sauves if r.get('type') == 'retard']
#     notif_result = envoyer_alertes_risque(contrat_id, risques_retard, token)

#     return Response({
#         'contrat_id':   contrat_id,
#         'risques':      risques_sauves,
#         'notification': notif_result,
#     })
# # ──────────────────────────────────────────────────────────────
# # VÉRIFICATION — notification_client.py
# # S'assurer que la fonction n'a PAS de filtre supplémentaire
# # ──────────────────────────────────────────────────────────────

# def envoyer_alertes_risque(contrat_id: int, risques: list, jwt_token: str) -> dict:
#     """
#     Envoie les risques reçus au service Notification Node.js.
#     Le filtrage par type (retard uniquement) est fait AVANT l'appel,
#     dans views.py — cette fonction envoie tout ce qu'elle reçoit.
#     """
#     sent_count = 0
#     errors = []

#     for risque in risques:   # ← PAS de filtre ici
#         try:
#             payload = {
#                 'contrat_id':  contrat_id,
#                 'code':        risque['code'],
#                 'type':        risque.get('type', 'retard'),
#                 'description': risque['description'],
#                 'severite':    risque.get('severite', 'moyen'),
#                 'article_ref': risque.get('article_ref', ''),
#                 'suggestion':  risque.get('suggestion', ''),
#             }
#             response = requests.post(
#                 f"{NOTIFICATION_SERVICE_URL}/notifications/risk-alerts/",
#                 json=payload,
#                 headers={"Authorization": f"Bearer {jwt_token}"},
#                 timeout=5,
#             )
#             if response.status_code in (200, 201):
#                 sent_count += 1
#             else:
#                 errors.append({
#                     'code':   risque['code'],
#                     'status': response.status_code,
#                     'detail': response.text[:200],
#                 })
#         except requests.exceptions.ConnectionError:
#             errors.append({
#                 'code':  risque['code'],
#                 'error': f'Service Notification injoignable ({NOTIFICATION_SERVICE_URL})',
#             })
#         except Exception as e:
#             errors.append({'code': risque['code'], 'error': str(e)})

#     return {'success': True, 'sent_count': sent_count, 'errors': errors}

@api_view(['POST'])
@authentication_classes([RemoteJWTAuthentication])
@permission_classes([IsResponsableDepartement])
def analyser_contrat(request, contrat_id):
    token = request.auth
    if not token:
        return Response({'error': 'Token non fourni'}, status=401)

    try:
        contrat = Contrat.objects.prefetch_related('risques').get(pk=contrat_id)
    except Contrat.DoesNotExist:
        return Response({'error': 'Contrat non trouvé'}, status=404)

    # ── Lire les risques RETARD depuis la BDD Django ──────────────────
    risques_retard_bdd = RisqueContrat.objects.filter(
        contrat=contrat,
        type_risque='retard',
        resolu=False,
    )

    # ── Construire la liste à envoyer à Node.js ───────────────────────
    risques_a_notifier = [
        {
            'code':             r.code,
            'type':             r.type_risque,
            'description':      r.description,
            'severite':         r.severite,
            'article_ref':      r.article_ref or '',
            'suggestion':       r.suggestion or '',
            'occurrence_count': r.occurrence_count,
            'escalade':         get_niveau_escalade(r.occurrence_count),
        }
        for r in risques_retard_bdd
    ]

    # ── Envoyer à Node.js ─────────────────────────────────────────────
    notif_result = envoyer_alertes_risque(contrat_id, risques_a_notifier, token)

    return Response({
        'contrat_id':      contrat_id,
        'risques_retard':  risques_a_notifier,
        'notification':    notif_result,
    })
# ──────────────────────────────────────────────────────────────
# RÉSULTAT ATTENDU après fix
# ──────────────────────────────────────────────────────────────
#
# POST /clm/contrats/15/analyser/
# → "sent_count": 1   (R-07 envoyé)
# → "errors": []
#
# GET /clm/contrats/15/alertes/
# → "count": 1
# → alerts[0].code == "R-07"
# # ══════════════════════════════════════════════════════════════
# GET /clm/contrats/{id}/alertes/
# ══════════════════════════════════════════════════════════════
@api_view(['GET'])
@authentication_classes([RemoteJWTAuthentication])      # ✅ MÊME auth que toutes les autres views
@permission_classes([IsResponsableDepartement])          # ✅ MÊME permission que toutes les autres views
def get_alertes_contrat(request, contrat_id):
    """
    Proxy vers le service Notification.
    Appelle /notifications/risk-alerts/ via le gateway.
    """
    token = request.auth
    if not token:
        return Response({'error': 'Token non fourni'}, status=401)

    alertes = get_alertes_retard(contrat_id, token)

    return Response({
        'contrat_id': contrat_id,
        'alerts':     alertes,
        'count':      len(alertes),
    })