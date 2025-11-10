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
    usuario = UsuarioSerializer(source='*', read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'usuario']
        read_only_fields = ['id']


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
        read_only_fields = ['id']
    
    def get_vagas_disponiveis(self, obj):
        inscricoes_confirmadas = obj.inscricoes.filter(
            status=Inscricao.Status.CONFIRMADA
        ).count()
        return max(0, obj.vagas - inscricoes_confirmadas)
    
    def validate(self, attrs):
        # Validar horários
        if 'hora_inicio' in attrs and 'hora_fim' in attrs:
            if attrs['hora_fim'] <= attrs['hora_inicio']:
                raise serializers.ValidationError({
                    "hora_fim": "Hora fim deve ser após a hora início."
                })
        
        # Validar se professor está no CT
        if 'ct' in attrs and 'professor' in attrs:
            ct = attrs['ct']
            professor = attrs['professor']
            if not ct.professores.filter(pk=professor.pk).exists():
                raise serializers.ValidationError({
                    "professor": "Professor não está associado a este CT."
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
        read_only_fields = ['id', 'criado_em']
    
    def validate(self, attrs):
        # Verificar se ainda há vagas
        treino = attrs.get('treino')
        if treino:
            inscricoes_confirmadas = treino.inscricoes.filter(
                status=Inscricao.Status.CONFIRMADA
            ).count()
            if inscricoes_confirmadas >= treino.vagas:
                raise serializers.ValidationError({
                    "treino": "Não há vagas disponíveis para este treino."
                })
        
        return attrs
