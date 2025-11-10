from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import CentroTreinamento, Inscricao, Treino, Usuario
from .serializers import (
    CentroTreinamentoSerializer,
    InscricaoSerializer,
    LoginSerializer,
    SignupSerializer,
    TreinoSerializer,
    UsuarioCompletoSerializer,
    UsuarioSerializer,
)

User = get_user_model()


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
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def perform_create(self, serializer):
        # Definir o usuário autenticado como gerente
        serializer.save(gerente=self.request.user)
    
    @action(detail=True, methods=['get'])
    def treinos(self, request, pk=None):
        """
        Listar todos os treinos de um CT específico
        """
        ct = self.get_object()
        treinos = ct.treinos.all()
        serializer = TreinoSerializer(treinos, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def add_professor(self, request, pk=None):
        """
        Adicionar professor ao CT
        """
        ct = self.get_object()
        professor_id = request.data.get('professor_id')
        
        try:
            user = User.objects.get(pk=professor_id)
            if user.usuario.tipo != Usuario.Tipo.PROFESSOR:
                return Response(
                    {'error': 'Usuário não é um professor'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            ct.professores.add(user)
            return Response({'message': 'Professor adicionado com sucesso'})
        
        except User.DoesNotExist:
            return Response(
                {'error': 'Usuário não encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def remove_professor(self, request, pk=None):
        """
        Remover professor do CT
        """
        ct = self.get_object()
        professor_id = request.data.get('professor_id')
        
        try:
            user = User.objects.get(pk=professor_id)
            ct.professores.remove(user)
            return Response({'message': 'Professor removido com sucesso'})
        
        except User.DoesNotExist:
            return Response(
                {'error': 'Usuário não encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )


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
        
        # Filtros opcionais
        ct_id = self.request.query_params.get('ct')
        data_min = self.request.query_params.get('data_min')
        data_max = self.request.query_params.get('data_max')
        
        if ct_id:
            queryset = queryset.filter(ct_id=ct_id)
        if data_min:
            queryset = queryset.filter(data__gte=data_min)
        if data_max:
            queryset = queryset.filter(data__lte=data_max)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(professor=self.request.user)
    
    @action(detail=True, methods=['get'])
    def inscricoes(self, request, pk=None):
        """
        Listar todas as inscrições de um treino específico
        """
        treino = self.get_object()
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
        
        # Filtros opcionais
        treino_id = self.request.query_params.get('treino')
        aluno_id = self.request.query_params.get('aluno')
        status_filter = self.request.query_params.get('status')
        
        if treino_id:
            queryset = queryset.filter(treino_id=treino_id)
        if aluno_id:
            queryset = queryset.filter(aluno_id=aluno_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(aluno=self.request.user)
    
    @action(detail=True, methods=['post'])
    def confirmar(self, request, pk=None):
        """
        Confirmar inscrição
        """
        inscricao = self.get_object()
        inscricao.status = Inscricao.Status.CONFIRMADA
        inscricao.save()
        serializer = self.get_serializer(inscricao)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cancelar(self, request, pk=None):
        """
        Cancelar inscrição
        """
        inscricao = self.get_object()
        inscricao.status = Inscricao.Status.CANCELADA
        inscricao.save()
        serializer = self.get_serializer(inscricao)
        return Response(serializer.data)


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
    
    @action(detail=False, methods=['put', 'patch'])
    def update_profile(self, request):
        """
        Atualizar perfil do usuário autenticado
        """
        user = request.user
        usuario = user.usuario
        
        # Atualizar dados do User
        user_fields = ['first_name', 'last_name', 'email']
        for field in user_fields:
            if field in request.data:
                setattr(user, field, request.data[field])
        user.save()
        
        # Atualizar dados do Usuario
        usuario_fields = ['telefone', 'nivel', 'certificacoes']
        for field in usuario_fields:
            if field in request.data:
                setattr(usuario, field, request.data[field])
        usuario.save()
        
        serializer = self.get_serializer(user)
        return Response(serializer.data)
