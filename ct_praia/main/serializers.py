from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import (
    AgendamentoTreino,
    CentroTreinamento,
    HorarioRecorrente,
    ProfessorCentroTreinamento,
    Inscricao,
    Treino,
    Usuario,
)

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
            'professores_nomes', 'latitude', 'longitude'
        ]
        read_only_fields = ['id']
    
    def get_professores_nomes(self, obj):
        return [p.get_full_name() or p.username for p in obj.professores.all()]


class ProfessorCentroTreinamentoSerializer(serializers.ModelSerializer):
    """Serializer para permissões de professor em um CT."""

    professor_nome = serializers.CharField(source='professor.get_full_name', read_only=True)

    class Meta:
        model = ProfessorCentroTreinamento
        fields = [
            'id', 'ct', 'professor', 'professor_nome',
            'pode_criar_treino', 'pode_cancelar_treino',
            'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['id', 'criado_em', 'atualizado_em']


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
            'vagas', 'vagas_disponiveis', 'nivel', 'observacoes',
            'agendado', 'agendamento'
        ]
        read_only_fields = ['id', 'agendado', 'agendamento']
    
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
        
        ct = attrs.get('ct') or getattr(self.instance, 'ct', None)
        professor = attrs.get('professor') or getattr(self.instance, 'professor', None)

        # Professor deve pertencer ao CT
        if ct and professor and not ct.professores.filter(pk=professor.pk).exists():
            raise serializers.ValidationError({
                "professor": "Professor não está associado a este CT."
            })

        request = self.context.get('request')
        if request and ct:
            user = request.user
            if not user.is_superuser:
                if not hasattr(user, 'usuario'):
                    raise serializers.ValidationError({"ct": "Usuário sem perfil associado."})
                if user.usuario.tipo == Usuario.Tipo.GERENTE:
                    if ct.gerente_id != user.id:
                        raise serializers.ValidationError({"ct": "Apenas o gerente do CT pode criar ou editar treinos aqui."})
                elif user.usuario.tipo == Usuario.Tipo.PROFESSOR:
                    # Professores só manipulam treinos nos quais são o professor
                    if professor and professor.id != user.id:
                        raise serializers.ValidationError({"professor": "Professores só podem manipular seus próprios treinos."})
                    if not ct.professores.filter(pk=user.pk).exists():
                        raise serializers.ValidationError({"ct": "Você não está associado a este Centro de Treinamento."})
                else:
                    raise serializers.ValidationError({"ct": "Somente gerente ou professor podem manipular treinos."})
        
        return attrs


class HorarioRecorrenteSerializer(serializers.ModelSerializer):
    dia_semana_label = serializers.CharField(source='get_dia_semana_display', read_only=True)

    class Meta:
        model = HorarioRecorrente
        fields = ['id', 'dia_semana', 'dia_semana_label', 'hora_inicio', 'hora_fim']
        read_only_fields = ['id', 'dia_semana_label']

    def validate(self, attrs):
        if attrs['hora_fim'] <= attrs['hora_inicio']:
            raise serializers.ValidationError({'hora_fim': 'Hora fim deve ser após a hora início.'})
        return attrs


class AgendamentoTreinoSerializer(serializers.ModelSerializer):
    horarios = HorarioRecorrenteSerializer(many=True)
    ct_nome = serializers.CharField(source='ct.nome', read_only=True)
    professor_nome = serializers.CharField(source='professor.get_full_name', read_only=True)

    class Meta:
        model = AgendamentoTreino
        fields = [
            'id', 'ct', 'ct_nome', 'professor', 'professor_nome',
            'modalidade', 'vagas', 'nivel', 'observacoes',
            'horarios', 'criado_em', 'atualizado_em'
        ]
        read_only_fields = ['id', 'professor_nome', 'criado_em', 'atualizado_em']

    def validate_horarios(self, value):
        if not value:
            raise serializers.ValidationError('Informe ao menos um dia/horário para o agendamento.')
        return value

    def validate(self, attrs):
        horarios = self.initial_data.get('horarios')
        if not horarios:
            raise serializers.ValidationError({'horarios': 'Informe ao menos um dia/horário.'})
        request = self.context.get('request')
        ct = attrs.get('ct') or getattr(self.instance, 'ct', None)
        professor = attrs.get('professor') or getattr(self.instance, 'professor', None)

        if request and ct and not request.user.is_superuser:
            user = request.user
            if not hasattr(user, 'usuario'):
                raise serializers.ValidationError({'ct': 'Usuário sem perfil associado.'})

            if user.usuario.tipo == Usuario.Tipo.GERENTE:
                if ct.gerente_id != user.id:
                    raise serializers.ValidationError({'ct': 'Apenas o gerente do CT pode gerenciar agendamentos deste CT.'})
            elif user.usuario.tipo == Usuario.Tipo.PROFESSOR:
                if professor and professor.id != user.id:
                    raise serializers.ValidationError({'professor': 'Professores só podem criar/editar agendamentos em que são responsáveis.'})
                if not ct.professores.filter(pk=user.pk).exists():
                    raise serializers.ValidationError({'ct': 'Você não está associado a este CT.'})
            else:
                raise serializers.ValidationError({'ct': 'Somente gerente ou professor podem gerenciar agendamentos.'})

        if ct and professor and not ct.professores.filter(pk=professor.pk).exists():
            raise serializers.ValidationError({'professor': 'Professor não está associado a este CT.'})

        return super().validate(attrs)

    def create(self, validated_data):
        horarios_data = validated_data.pop('horarios', [])
        agendamento = AgendamentoTreino.objects.create(**validated_data)
        self._recreate_horarios(agendamento, horarios_data)
        return agendamento

    def update(self, instance, validated_data):
        horarios_data = validated_data.pop('horarios', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if horarios_data is not None:
            instance.horarios.all().delete()
            self._recreate_horarios(instance, horarios_data)
        return instance

    def _recreate_horarios(self, agendamento, horarios_data):
        for horario in horarios_data:
            HorarioRecorrente.objects.create(
                agendamento=agendamento,
                dia_semana=horario['dia_semana'],
                hora_inicio=horario['hora_inicio'],
                hora_fim=horario['hora_fim'],
            )


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
