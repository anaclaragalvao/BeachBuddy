from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import AgendamentoTreino, CentroTreinamento, Inscricao, ProfessorCentroTreinamento, Treino, Usuario
from .serializers import (
    AgendamentoTreinoSerializer,
    CentroTreinamentoSerializer,
    ProfessorCentroTreinamentoSerializer,
    InscricaoSerializer,
    LoginSerializer,
    SignupSerializer,
    TreinoSerializer,
    UpdateProfileSerializer,
    UsuarioCompletoSerializer,
    UsuarioSerializer,
)
from .services import regenerate_agendamento_ocorrencias

User = get_user_model()


def _is_gerente_do_ct(user, ct: CentroTreinamento) -> bool:
    return bool(user.is_superuser or (hasattr(user, "usuario") and user.usuario.tipo == Usuario.Tipo.GERENTE and ct.gerente_id == user.id))


def _professor_vinculo(ct: CentroTreinamento, professor_id: int | None):
    if not professor_id:
        return None
    return ct.get_vinculo_professor(professor_id)


def _require_professor_associado(ct: CentroTreinamento, professor_id: int):
    if not _professor_vinculo(ct, professor_id):
        raise PermissionDenied("Professor não está associado a este CT.")


@swagger_auto_schema(
    method='post',
    request_body=SignupSerializer,
    responses={
        201: openapi.Response(
            description='Usuário cadastrado com sucesso',
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'user': openapi.Schema(type=openapi.TYPE_OBJECT, description='Dados completos do usuário'),
                    'token': openapi.Schema(type=openapi.TYPE_STRING, description='Access token JWT'),
                    'refresh': openapi.Schema(type=openapi.TYPE_STRING, description='Refresh token JWT'),
                }
            )
        ),
        400: 'Dados inválidos'
    },
    operation_description='Cadastro de novo usuário (Aluno, Professor ou Gerente). Retorna o usuário criado e tokens JWT.'
)
@api_view(['POST'])
@permission_classes([AllowAny])
def signup_view(request):
    """
    Cadastro de novo usuário (Aluno, Professor ou Gerente)
    """
    serializer = SignupSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        
        # Gerar tokens JWT
        refresh = RefreshToken.for_user(user)
        
        # Buscar dados completos do usuário
        usuario_completo = UsuarioCompletoSerializer(user).data
        
        return Response({
            'user': usuario_completo,
            'token': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    request_body=LoginSerializer,
    responses={
        200: openapi.Response(
            description='Login realizado com sucesso',
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'user': openapi.Schema(type=openapi.TYPE_OBJECT, description='Dados completos do usuário'),
                    'token': openapi.Schema(type=openapi.TYPE_STRING, description='Access token JWT'),
                    'refresh': openapi.Schema(type=openapi.TYPE_STRING, description='Refresh token JWT'),
                }
            )
        ),
        401: 'Credenciais inválidas'
    },
    operation_description='Login de usuário com username e password. Retorna dados do usuário e tokens JWT.'
)
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Login de usuário (retorna JWT token)
    """
    from django.contrib.auth import authenticate
    
    username = request.data.get('username')
    password = request.data.get('password')
    
    user = authenticate(username=username, password=password)
    
    if user is not None:
        refresh = RefreshToken.for_user(user)
        usuario_completo = UsuarioCompletoSerializer(user).data
        
        return Response({
            'user': usuario_completo,
            'token': str(refresh.access_token),
            'refresh': str(refresh),
        })
    
    return Response(
        {'error': 'Credenciais inválidas'},
        status=status.HTTP_401_UNAUTHORIZED
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def metrics_view(request):
    """
    Retorna métricas públicas da plataforma
    """
    hoje = timezone.now().date()
    
    metrics = {
        'metric_cts': CentroTreinamento.objects.count(),
        'metric_professores': Usuario.objects.filter(tipo=Usuario.Tipo.PROFESSOR).count(),
        'metric_treinos': Treino.objects.filter(data__gte=hoje).count(),
        'metric_alunos': Usuario.objects.filter(tipo=Usuario.Tipo.ALUNO).count(),
    }
    
    return Response(metrics)


class CentroTreinamentoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciar Centros de Treinamento
    
    list: Listar todos os CTs (público)
    retrieve: Detalhes de um CT (público)
    create: Criar novo CT (apenas gerentes autenticados)
    update/partial_update: Atualizar CT (apenas gerente responsável)
    destroy: Deletar CT (apenas gerente responsável)
    """
    queryset = CentroTreinamento.objects.all()
    serializer_class = CentroTreinamentoSerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'treinos']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        """Para ações de escrita, limita aos CTs do gerente autenticado."""
        qs = super().get_queryset()
        user = self.request.user

        # Leitura é pública (inclui ct/{id}/treinos)
        if self.action in ['list', 'retrieve', 'treinos']:
            return qs

        if user.is_superuser:
            return qs

        # Para create/update/destroy/add_professor etc: somente gerente do CT
        if not hasattr(user, 'usuario') or user.usuario.tipo != Usuario.Tipo.GERENTE:
            return qs.none()
        return qs.filter(gerente=user)
    
    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_superuser and (not hasattr(user, 'usuario') or user.usuario.tipo != Usuario.Tipo.GERENTE):
            raise PermissionDenied('Apenas gerentes podem criar Centros de Treinamento.')
        serializer.save(gerente=user)
    
    @swagger_auto_schema(
        method='get',
        operation_description='Retorna apenas os Centros de Treinamento do gerente autenticado. Requer autenticação JWT via header Authorization: Bearer {token}',
        responses={
            200: CentroTreinamentoSerializer(many=True),
            401: 'Token inválido ou ausente',
            403: 'Usuário não é gerente'
        },
        security=[{'Bearer': []}]
    )
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def meus_cts(self, request):
        """
        Listar apenas os CTs do gerente autenticado
        """
        user = request.user
        
        # Debug logs
        print(f"User: {user}, Authenticated: {user.is_authenticated}")
        print(f"Has usuario: {hasattr(user, 'usuario')}")
        
        if hasattr(user, 'usuario'):
            print(f"Tipo: {user.usuario.tipo}")
        
        # Verificar se o usuário tem perfil
        if not hasattr(user, 'usuario'):
            return Response(
                {'detail': 'Usuário sem perfil associado'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar se é gerente
        if user.usuario.tipo != Usuario.Tipo.GERENTE:
            return Response(
                {'detail': 'Apenas gerentes podem acessar este endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Filtrar CTs do gerente
        cts = CentroTreinamento.objects.filter(gerente=user)
        print(f"CTs encontrados: {cts.count()}")
        serializer = self.get_serializer(cts, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def treinos(self, request, pk=None):
        """
        Listar todos os treinos de um CT específico
        """
        ct = self.get_object()
        hoje = timezone.localdate()
        treinos = ct.treinos.filter(data__gte=hoje)
        serializer = TreinoSerializer(treinos, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def add_professor(self, request, pk=None):
        """
        Adicionar professor ao CT
        """
        ct = self.get_object()
        if not _is_gerente_do_ct(request.user, ct):
            raise PermissionDenied('Apenas o gerente do CT pode adicionar professores.')
        professor_id = request.data.get('professor_id')
        
        try:
            user = User.objects.get(pk=professor_id)
            if not hasattr(user, 'usuario') or user.usuario.tipo != Usuario.Tipo.PROFESSOR:
                return Response(
                    {'error': 'Usuário não é um professor'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Through model created with default flags (False)
            ProfessorCentroTreinamento.objects.get_or_create(ct=ct, professor=user)
            return Response({'message': 'Professor adicionado com sucesso'})
        
        except User.DoesNotExist:
            return Response(
                {'error': 'Usuário não encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )


class ProfessorCentroTreinamentoViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Gerencia flags de permissão por professor em um CT.

    - Gerente: pode listar/editar vínculos dos seus CTs
    - Professor: pode apenas listar/consultar seus próprios vínculos
    """

    queryset = ProfessorCentroTreinamento.objects.select_related('ct', 'professor')
    serializer_class = ProfessorCentroTreinamentoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        if not hasattr(user, 'usuario'):
            return qs.none()
        if user.usuario.tipo == Usuario.Tipo.GERENTE:
            return qs.filter(ct__gerente=user)
        if user.usuario.tipo == Usuario.Tipo.PROFESSOR:
            return qs.filter(professor=user)
        return qs.none()

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not _is_gerente_do_ct(request.user, instance.ct):
            raise PermissionDenied('Apenas o gerente do CT pode alterar permissões de professores.')
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not _is_gerente_do_ct(request.user, instance.ct):
            raise PermissionDenied('Apenas o gerente do CT pode alterar permissões de professores.')
        return super().partial_update(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def remove_professor(self, request, pk=None):
        """
        Remover professor do CT
        """
        ct = self.get_object()
        if not _is_gerente_do_ct(request.user, ct):
            raise PermissionDenied('Apenas o gerente do CT pode remover professores.')
        professor_id = request.data.get('professor_id')
        
        try:
            user = User.objects.get(pk=professor_id)
            ProfessorCentroTreinamento.objects.filter(ct=ct, professor=user).delete()
            return Response({'message': 'Professor removido com sucesso'})
        
        except User.DoesNotExist:
            return Response(
                {'error': 'Usuário não encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )


class AgendamentoTreinoViewSet(viewsets.ModelViewSet):
    """ViewSet responsável pelo CRUD dos agendamentos de treinos recorrentes."""

    queryset = (
        AgendamentoTreino.objects
        .select_related('ct', 'professor')
        .prefetch_related('horarios')
    )
    serializer_class = AgendamentoTreinoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        if not hasattr(user, 'usuario'):
            return qs.none()
        if user.usuario.tipo == Usuario.Tipo.GERENTE:
            return qs.filter(ct__gerente=user)
        if user.usuario.tipo == Usuario.Tipo.PROFESSOR:
            return qs.filter(professor=user)
        return qs.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_superuser:
            instance = serializer.save()
            regenerate_agendamento_ocorrencias(instance)
            return

        if not hasattr(user, 'usuario'):
            raise PermissionDenied('Usuário sem perfil associado.')

        ct = serializer.validated_data.get('ct')
        professor = serializer.validated_data.get('professor')

        if user.usuario.tipo == Usuario.Tipo.GERENTE:
            if not ct or ct.gerente_id != user.id:
                raise PermissionDenied('Apenas o gerente do CT pode criar agendamentos.')
            if not professor:
                raise ValidationError({'professor': 'Informe o professor responsável pelo agendamento.'})
            _require_professor_associado(ct, professor.id)
            instance = serializer.save()
        elif user.usuario.tipo == Usuario.Tipo.PROFESSOR:
            vinculo = _professor_vinculo(ct, user.id)
            if not vinculo:
                raise PermissionDenied('Você não está associado a este CT.')
            if not vinculo.pode_criar_treino:
                raise PermissionDenied('Você não tem permissão para criar agendamentos neste CT.')
            instance = serializer.save(professor=user)
        else:
            raise PermissionDenied('Somente gerente ou professor podem criar agendamentos.')

        regenerate_agendamento_ocorrencias(instance)

    def perform_update(self, serializer):
        instance = self.get_object()
        self._ensure_can_mutate(instance, self.request.user, action='update')
        instance = serializer.save()
        regenerate_agendamento_ocorrencias(instance)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self._ensure_can_mutate(instance, request.user, action='destroy')
        return super().destroy(request, *args, **kwargs)

    def _ensure_can_mutate(self, instance, user, action: str):
        if user.is_superuser:
            return
        if not hasattr(user, 'usuario'):
            raise PermissionDenied('Usuário sem perfil associado.')

        if user.usuario.tipo == Usuario.Tipo.GERENTE:
            if instance.ct.gerente_id != user.id:
                raise PermissionDenied('Você não pode alterar este agendamento.')
            return

        if user.usuario.tipo == Usuario.Tipo.PROFESSOR:
            if instance.professor_id != user.id:
                raise PermissionDenied('Você não pode alterar este agendamento.')
            vinculo = _professor_vinculo(instance.ct, user.id)
            if not vinculo:
                raise PermissionDenied('Você não está associado a este CT.')
            if action == 'destroy':
                if not vinculo.pode_cancelar_treino:
                    raise PermissionDenied('Você não tem permissão para cancelar agendamentos neste CT.')
                return
            if not vinculo.pode_criar_treino:
                raise PermissionDenied('Você não tem permissão para alterar agendamentos neste CT.')
            return

        raise PermissionDenied('Você não pode alterar este agendamento.')


class TreinoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciar Treinos
    
    list: Listar todos os treinos (filtros disponíveis: ct, data_min, data_max)
    retrieve: Detalhes de um treino
    create: Criar novo treino (apenas professores)
    update/partial_update: Atualizar treino (apenas professor responsável)
    destroy: Deletar treino (apenas professor responsável)
    """
    queryset = Treino.objects.select_related('ct', 'professor').all()
    serializer_class = TreinoSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()

        # Regra de plataforma: apenas treinos futuros por padrão
        hoje = timezone.localdate()
        data_min_effective = self.request.query_params.get('data_min') or hoje.isoformat()
        try:
            # Se o cliente passar uma data anterior a hoje, mantemos hoje (apenas futuros)
            if data_min_effective < hoje.isoformat():
                data_min_effective = hoje.isoformat()
        except Exception:
            data_min_effective = hoje.isoformat()

        queryset = queryset.filter(data__gte=data_min_effective)
        
        # Filtros opcionais
        ct_id = self.request.query_params.get('ct')
        data_max = self.request.query_params.get('data_max')
        
        if ct_id:
            queryset = queryset.filter(ct_id=ct_id)
        if data_max:
            queryset = queryset.filter(data__lte=data_max)

        user = self.request.user
        if user.is_superuser:
            return queryset
        if not hasattr(user, 'usuario'):
            return queryset.none()
        if user.usuario.tipo == Usuario.Tipo.GERENTE:
            return queryset.filter(ct__gerente=user)
        if user.usuario.tipo == Usuario.Tipo.PROFESSOR:
            return queryset.filter(professor=user)
        # ALUNO: pode listar treinos futuros para se inscrever
        return queryset
    
    def perform_create(self, serializer):
        user = self.request.user
        if user.is_superuser:
            serializer.save()
            return

        if not hasattr(user, 'usuario'):
            raise PermissionDenied('Usuário sem perfil associado.')

        ct = serializer.validated_data.get('ct')
        professor = serializer.validated_data.get('professor')

        if user.usuario.tipo == Usuario.Tipo.GERENTE:
            if not ct or ct.gerente_id != user.id:
                raise PermissionDenied('Apenas o gerente do CT pode criar treinos.')
            if not professor:
                raise ValidationError({'professor': 'Informe o professor responsável pelo treino.'})
            _require_professor_associado(ct, professor.id)
            serializer.save()
            return

        if user.usuario.tipo == Usuario.Tipo.PROFESSOR:
            vinculo = _professor_vinculo(ct, user.id)
            if not vinculo:
                raise PermissionDenied('Você não está associado a este CT.')
            if not vinculo.pode_criar_treino:
                raise PermissionDenied('Você não tem permissão para criar treinos neste CT.')
            serializer.save(professor=user)
            return

        raise PermissionDenied('Somente gerente ou professor podem criar treinos.')

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        self._ensure_manual(instance)
        self._ensure_can_mutate(instance, request.user, action='update')
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        self._ensure_manual(instance)
        self._ensure_can_mutate(instance, request.user, action='update')
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self._ensure_manual(instance)
        self._ensure_can_mutate(instance, request.user, action='destroy')
        return super().destroy(request, *args, **kwargs)

    def _ensure_manual(self, instance: Treino):
        if instance.agendado:
            raise ValidationError('Treinos oriundos de agendamento devem ser alterados no próprio agendamento.')

    def _ensure_can_mutate(self, instance: Treino, user, action: str):
        if user.is_superuser:
            return
        if not hasattr(user, 'usuario'):
            raise PermissionDenied('Usuário sem perfil associado.')
        if user.usuario.tipo == Usuario.Tipo.GERENTE:
            if instance.ct.gerente_id != user.id:
                raise PermissionDenied('Você não pode alterar este treino.')
            return
        if user.usuario.tipo == Usuario.Tipo.PROFESSOR:
            if instance.professor_id != user.id:
                raise PermissionDenied('Você não pode alterar este treino.')
            vinculo = _professor_vinculo(instance.ct, user.id)
            if not vinculo:
                raise PermissionDenied('Você não está associado a este CT.')
            if action == 'destroy':
                if not vinculo.pode_cancelar_treino:
                    raise PermissionDenied('Você não tem permissão para cancelar treinos neste CT.')
                return
            if not vinculo.pode_criar_treino:
                raise PermissionDenied('Você não tem permissão para alterar treinos neste CT.')
            return
        raise PermissionDenied('Você não pode alterar este treino.')
    
    @action(detail=True, methods=['get'])
    def inscricoes(self, request, pk=None):
        """
        Listar todas as inscrições de um treino específico
        """
        treino = self.get_object()

        user = request.user
        if not (user.is_superuser or treino.professor_id == user.id or _is_gerente_do_ct(user, treino.ct)):
            raise PermissionDenied('Você não pode ver as inscrições deste treino.')

        inscricoes = treino.inscricoes.all()
        serializer = InscricaoSerializer(inscricoes, many=True)
        return Response(serializer.data)


class InscricaoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciar Inscrições
    
    list: Listar inscrições (filtros: treino, aluno, status)
    retrieve: Detalhes de uma inscrição
    create: Criar nova inscrição (alunos)
    update/partial_update: Atualizar status da inscrição
    destroy: Cancelar inscrição
    """
    queryset = Inscricao.objects.select_related('treino', 'aluno').all()
    serializer_class = InscricaoSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()

        user = self.request.user
        if user.is_superuser:
            scoped = queryset
        elif not hasattr(user, 'usuario'):
            scoped = queryset.none()
        elif user.usuario.tipo == Usuario.Tipo.ALUNO:
            scoped = queryset.filter(aluno=user)
        elif user.usuario.tipo == Usuario.Tipo.PROFESSOR:
            scoped = queryset.filter(treino__professor=user)
        elif user.usuario.tipo == Usuario.Tipo.GERENTE:
            scoped = queryset.filter(treino__ct__gerente=user)
        else:
            scoped = queryset.none()
        
        # Filtros opcionais
        treino_id = self.request.query_params.get('treino')
        aluno_id = self.request.query_params.get('aluno')
        status_filter = self.request.query_params.get('status')
        
        if treino_id:
            scoped = scoped.filter(treino_id=treino_id)
        if aluno_id:
            scoped = scoped.filter(aluno_id=aluno_id)
        if status_filter:
            scoped = scoped.filter(status=status_filter)
        
        return scoped
    
    def perform_create(self, serializer):
        user = self.request.user
        if not hasattr(user, 'usuario') or user.usuario.tipo != Usuario.Tipo.ALUNO:
            raise PermissionDenied('Apenas alunos podem se inscrever em treinos.')
        serializer.save(aluno=user)
    
    @action(detail=True, methods=['post'])
    def confirmar(self, request, pk=None):
        """
        Confirmar inscrição
        """
        inscricao = self.get_object()
        if not request.user.is_superuser and inscricao.aluno_id != request.user.id:
            raise PermissionDenied('Você não pode confirmar esta inscrição.')
        inscricao.status = Inscricao.Status.CONFIRMADA
        inscricao.save()
        serializer = self.get_serializer(inscricao)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cancelar(self, request, pk=None):
        """
        Cancelar inscrição (deleta do banco para permitir nova inscrição futura)
        """
        inscricao = self.get_object()
        if not request.user.is_superuser and inscricao.aluno_id != request.user.id:
            raise PermissionDenied('Você não pode cancelar esta inscrição.')
        inscricao.delete()
        return Response(
            {'message': 'Inscrição cancelada com sucesso'},
            status=status.HTTP_200_OK
        )

    def destroy(self, request, *args, **kwargs):
        # Mantém consistência: excluir inscrição = cancelar, mas só o aluno dono
        inscricao = self.get_object()
        if not request.user.is_superuser and inscricao.aluno_id != request.user.id:
            raise PermissionDenied('Você não pode cancelar esta inscrição.')
        return super().destroy(request, *args, **kwargs)


class UsuarioViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para consultar usuários (somente leitura)
    
    list: Listar usuários (filtros: tipo)
    retrieve: Detalhes de um usuário
    me: Dados do usuário autenticado
    """
    queryset = User.objects.select_related('usuario').all()
    serializer_class = UsuarioCompletoSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtro por tipo
        tipo = self.request.query_params.get('tipo')
        if tipo:
            queryset = queryset.filter(usuario__tipo=tipo)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """
        Retorna dados do usuário autenticado
        """
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @swagger_auto_schema(
        method='patch',
        request_body=UpdateProfileSerializer,
        responses={
            200: UsuarioCompletoSerializer,
            400: 'Dados inválidos'
        }
    )
    @action(detail=False, methods=['patch'])
    def update_profile(self, request):
        """
        Atualizar perfil do usuário autenticado.
        
        Campos editáveis:
        - first_name, last_name (do User)
        - telefone, nivel, certificacoes (do Usuario)
        
        Campos NÃO editáveis (ignorados se enviados):
        - username, email, tipo
        """
        user = request.user
        usuario = user.usuario
        
        # Validar dados com o serializer
        serializer = UpdateProfileSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Atualizar apenas campos editáveis do User
        user_fields = ['first_name', 'last_name']
        for field in user_fields:
            if field in serializer.validated_data:
                setattr(user, field, serializer.validated_data[field])
        user.save()
        
        # Atualizar apenas campos editáveis do Usuario
        usuario_fields = ['telefone', 'nivel', 'certificacoes']
        for field in usuario_fields:
            if field in serializer.validated_data:
                setattr(usuario, field, serializer.validated_data[field])
        usuario.save()
        
        # Retornar dados completos atualizados
        response_serializer = UsuarioCompletoSerializer(user)
        return Response(response_serializer.data)
