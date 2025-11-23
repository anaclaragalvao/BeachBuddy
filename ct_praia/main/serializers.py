from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import CentroTreinamento, Inscricao, Treino, Usuario

User = get_user_model()


class LoginSerializer(serializers.Serializer):
    """Serializer para login de usuários"""
    username = serializers.CharField(required=True, help_text="Nome de usuário")
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        help_text="Senha do usuário"
    )


class UserSerializer(serializers.ModelSerializer):
    """Serializer para o modelo User padrão do Django"""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


class UsuarioSerializer(serializers.ModelSerializer):
    """Serializer para o perfil de usuário estendido"""
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Usuario
        fields = ['id', 'user', 'tipo', 'telefone', 'nivel', 'certificacoes']
        read_only_fields = ['id']


class UsuarioCompletoSerializer(serializers.ModelSerializer):
    """Serializer completo com dados do User e Usuario"""
    usuario = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'usuario']
        read_only_fields = ['id']
    
    def get_usuario(self, obj):
        """Retorna os dados do perfil Usuario"""
        try:
            return {
                'tipo': obj.usuario.tipo,
                'telefone': obj.usuario.telefone,
                'nivel': obj.usuario.nivel,
                'certificacoes': obj.usuario.certificacoes,
            }
        except Usuario.DoesNotExist:
            return None


class UpdateProfileSerializer(serializers.Serializer):
    """Serializer para atualização de perfil do usuário"""
    # Campos do User que podem ser editados
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    
    # Campos do Usuario que podem ser editados
    telefone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    nivel = serializers.CharField(max_length=50, required=False, allow_blank=True)
    certificacoes = serializers.CharField(required=False, allow_blank=True)
    
    # Campos somente leitura (não podem ser alterados)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    tipo = serializers.CharField(read_only=True)


class SignupSerializer(serializers.ModelSerializer):
    """Serializer para cadastro de novos usuários"""
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all())]
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )
    password2 = serializers.CharField(write_only=True, required=True)
    
    # Campos do Usuario
    tipo = serializers.ChoiceField(choices=Usuario.Tipo.choices, required=True)
    telefone = serializers.CharField(required=False, allow_blank=True)
    nivel = serializers.CharField(required=False, allow_blank=True)
    certificacoes = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password2',
            'first_name', 'last_name', 'tipo', 'telefone', 
            'nivel', 'certificacoes'
        ]
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True}
        }
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError(
                {"password": "As senhas não coincidem."}
            )
        return attrs
    
    def create(self, validated_data):
        # Remover campos que não são do User
        password2 = validated_data.pop('password2')
        tipo = validated_data.pop('tipo')
        telefone = validated_data.pop('telefone', '')
        nivel = validated_data.pop('nivel', '')
        certificacoes = validated_data.pop('certificacoes', '')
        
        # Criar usuário
        user = User.objects.create_user(**validated_data)
        
        # Criar perfil Usuario
        Usuario.objects.create(
            user=user,
            tipo=tipo,
            telefone=telefone,
            nivel=nivel,
            certificacoes=certificacoes
        )
        
        return user


class CentroTreinamentoSerializer(serializers.ModelSerializer):
    """Serializer para Centro de Treinamento"""
    gerente_nome = serializers.CharField(
        source='gerente.get_full_name',
        read_only=True
    )
    professores_nomes = serializers.SerializerMethodField()
    
    class Meta:
        model = CentroTreinamento
        fields = [
            'id', 'nome', 'endereco', 'contato', 'modalidades',
            'cnpj', 'gerente', 'gerente_nome', 'professores', 
            'professores_nomes'
        ]
        read_only_fields = ['id']
    
    def get_professores_nomes(self, obj):
        return [p.get_full_name() or p.username for p in obj.professores.all()]


class TreinoSerializer(serializers.ModelSerializer):
    """Serializer para Treino"""
    ct_nome = serializers.CharField(source='ct.nome', read_only=True)
    professor_nome = serializers.CharField(
        source='professor.get_full_name',
        read_only=True
    )
    vagas_disponiveis = serializers.SerializerMethodField()
    
    class Meta:
        model = Treino
        fields = [
            'id', 'ct', 'ct_nome', 'professor', 'professor_nome',
            'modalidade', 'data', 'hora_inicio', 'hora_fim',
            'vagas', 'vagas_disponiveis', 'nivel', 'observacoes'
        ]
        read_only_fields = ['id', 'professor']  # professor é setado automaticamente
    
    def get_vagas_disponiveis(self, obj):
        # Contar inscrições confirmadas e pendentes (excluir canceladas)
        inscricoes_ativas = obj.inscricoes.filter(
            status__in=[Inscricao.Status.CONFIRMADA, Inscricao.Status.PENDENTE]
        ).count()
        return max(0, obj.vagas - inscricoes_ativas)
    
    def validate(self, attrs):
        # Validar horários
        if 'hora_inicio' in attrs and 'hora_fim' in attrs:
            if attrs['hora_fim'] <= attrs['hora_inicio']:
                raise serializers.ValidationError({
                    "hora_fim": "Hora fim deve ser após a hora início."
                })
        
        # Validar se professor está no CT (apenas quando professor é fornecido)
        # Na criação via API, o professor é setado no perform_create, então não estará em attrs
        if 'ct' in attrs and 'professor' in attrs:
            ct = attrs['ct']
            professor = attrs['professor']
            if not ct.professores.filter(pk=professor.pk).exists():
                raise serializers.ValidationError({
                    "professor": "Professor não está associado a este CT."
                })
        
        # Se estamos criando (não tem professor em attrs), validar com request.user
        request = self.context.get('request')
        if request and 'ct' in attrs and 'professor' not in attrs:
            ct = attrs['ct']
            if not ct.professores.filter(pk=request.user.pk).exists():
                raise serializers.ValidationError({
                    "ct": "Você não está associado a este Centro de Treinamento."
                })
        
        return attrs


class InscricaoSerializer(serializers.ModelSerializer):
    """Serializer para Inscrição"""
    treino_detalhes = TreinoSerializer(source='treino', read_only=True)
    aluno_nome = serializers.CharField(
        source='aluno.get_full_name',
        read_only=True
    )
    
    class Meta:
        model = Inscricao
        fields = [
            'id', 'treino', 'treino_detalhes', 'aluno', 'aluno_nome',
            'status', 'criado_em'
        ]
        read_only_fields = ['id', 'aluno', 'criado_em']
    
    def validate(self, attrs):
        # Verificar se o aluno já está inscrito neste treino
        treino = attrs.get('treino')
        request = self.context.get('request')
        
        if treino and request:
            # Verificar se já existe uma inscrição
            inscricao_existente = Inscricao.objects.filter(
                treino=treino,
                aluno=request.user
            ).first()
            
            if inscricao_existente:
                raise serializers.ValidationError({
                    "treino": "Você já está inscrito neste treino."
                })
        
        # Verificar se ainda há vagas (contar apenas confirmadas e pendentes)
        if treino:
            inscricoes_ativas = treino.inscricoes.filter(
                status__in=[Inscricao.Status.CONFIRMADA, Inscricao.Status.PENDENTE]
            ).count()
            if inscricoes_ativas >= treino.vagas:
                raise serializers.ValidationError({
                    "treino": "Não há vagas disponíveis para este treino."
                })
        
        return attrs
