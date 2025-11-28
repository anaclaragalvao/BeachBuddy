<div align="center">

# BeachBuddy 🏖️
Plataforma web para conectar alunos, professores e gerentes de Centros de Treinamento de beach sports (vôlei de praia, futevôlei etc.). Projeto desenvolvido para a disciplina INF1407.

</div>

## 1. Integrantes
- Ana Clara Pinho Galvão (2220505)
- Felipe Fortini Franco (2220501)

## 2. Visão Geral 
Desenvolvemos o BeachBuddy para resolver um problema simples: a dificuldade de descobrir treinos disponíveis, gerenciar inscrições e organizar a agenda entre múltiplos Centros de Treinamento (CTs). A plataforma unifica três perfis de uso:
1. Aluno: encontra e se inscreve rapidamente em treinos com vagas.
2. Professor: cria e administra sua grade de treinos sem choques de horário.
3. Gerente: cadastra e gerencia seus CTs, associando professores e acompanhando métricas básicas.

O foco foi entregar um MVP funcional, consistente visualmente e com regras de negócio claras (capacidade, conflito de horários, associação professor–CT, unicidade de inscrição).

## 3. Principais Funcionalidades
### Autenticação e Perfis
- Cadastro separado para Aluno, Professor e Gerente (cada um com fluxo próprio).
- Perfil estendido (`Usuario`) sem substituir o `AUTH_USER_MODEL` do Django.
- Redirecionamento pós-login contextual: aluno → meus treinos, professor → dashboard, gerente → meus CTs.

### Aluno
- Lista “Meus Treinos” mostrando apenas inscrições futuras ativas (pendentes/confirmadas).
- Cancelamento de inscrição (soft via status = CANCELADA).
- Wizard de inscrição: (1) escolher CT → (2) escolher treino dentro desse CT.
- Botões de inscrição só aparecem se há vagas disponíveis e o aluno ainda não está inscrito.

### Professor
- Dashboard consolidado com:
  - Filtros por data, período (hoje/semana/mês) e CT.
  - Métricas (treinos hoje / semana / mês / próximo treino e vagas disponíveis).
  - Criação/Edição/Exclusão de treinos em modal (UX mais fluida) ou via telas CRUD tradicionais (fallback).
- Validação de conflito de horário (mesmo professor, mesmo CT, intervalo sobreposto).
- Cálculo dinâmico de vagas disponíveis (vagas - inscrições confirmadas).

### Gerente
- Cadastro de novos Centros de Treinamento.
- Associação e gerenciamento do conjunto de professores autorizados por CT.
- Painel “Meus CTs” com métricas agregadas (quantidade de CTs, professores distintos, treinos futuros).

### Regras de Negócio Implementadas
- Um professor só pode criar treino em CT ao qual está associado.
- Não é possível criar treino com hora_fim <= hora_inicio.
- Não é possível sobrepor dois treinos do mesmo professor no mesmo CT com interseção de horário.
- Capacidade: novas inscrições (ou reativação de inscrição cancelada) são bloqueadas quando vagas esgotam.
- Unicidade de inscrição (aluno + treino) garantida na modelagem e reforçada na lógica.

## 4. Tecnologias e Dependências
Ambiente principal:
- Python 3.11.x
- Django 4.1.7

Bibliotecas listadas em `requirements.txt`:
- asgiref (infra Django ASGI)
- Django (framework principal)
- gunicorn (servidor WSGI para deploy Linux/Heroku; em Windows utilize `runserver` localmente)
- packaging (utilitário interno de versões)
- sqlparse (formatação SQL usada pelo Django)
- typing_extensions (tipagem para recursos futuros/backports)
- tzdata (informação de fuso horário em ambientes sem sistema operacional provendo zoneinfo)
- whitenoise (servir arquivos estáticos em produção)

## 5. O que Funciona Bem
- Tudo

## 6. Como Executar Localmente
### Tem que comentar algumas linhas no settings.py allowed_hosts e csrf_trusted_origins da producao e descomentar a do local.
1. Criar e ativar virtualenv (Windows PowerShell):
   ```powershell
   python -m venv .venv; .\.venv\Scripts\Activate.ps1
   ```
2. Instalar dependências:
   ```powershell
   pip install -r requirements.txt
   ```
3. Migrar banco:
   ```powershell
   python ct_praia/manage.py migrate
   ```
4. Criar superusuário (opcional):
   ```powershell
   python ct_praia/manage.py createsuperuser
   ```
5. Rodar servidor de desenvolvimento:
   ```powershell
   python ct_praia/manage.py runserver
   ```
6. Acessar http://127.0.0.1:8000/


## ERD (ASCII)

```text
+---------------------------+
|          Usuario          |
+---------------------------+
| id (PK)                   |  (n)         
| tipo: {ALUNO, PROFESSOR,  |---------------------------|
|        GERENTE}           |                           |
| nome, email, ...          |                           |
+---------------------------+                           |
         (1)|                                           |
            | (professor)                               |
            |                                           |(aluno)
         (n)|                                           |
        +---------------------------+                   |
        |          Treino           |                   |
        +---------------------------+                   |
        | id (PK)                   |                   |
        | ct_id (FK -> CT.id)       |                   |
        | professor_id (FK -> Usuario.id) |             |
        | modalidade                |                   |
        | data                      |                   |
        | hora_inicio, hora_fim     |                   |
        | vagas                     |                   |
        | nivel                     |--------           |
        | observacoes               |(1)    |           |
        +---------------------------+       |           |
            |(n)                            |           |
            |                               |           |
            |                               |           |
            |                               |           |
            |(1)                         (n)|           |(n)
+---------------------------+      +---------------------------+
|   CentroTreinamento (CT)  |      |         Inscricao         |
+---------------------------+      +---------------------------+
| id (PK)                   |      | id (PK)                   |
| nome                      |      | treino_id (FK -> Treino.id) 
| endereco                  |      | aluno_id (FK -> Usuario.id) 
| contato                   |      | status: {PENDENTE,         |
| modalidades (texto)       |      |          CONFIRMADA,       |
+---------------------------+      |          CANCELADA}        |
                                   | criado_em                  |
                                   +---------------------------+

Cardinalidades:
- Usuario (PROFESSOR) (1) ─── (n) Treino
- CentroTreinamento (1) ─── (n) Treino
- Treino (1) ─── (n) Inscricao
- Usuario (ALUNO) (1) ─── (n) Inscricao

Restrições/Notas:
- Treino.hora_fim > Treino.hora_inicio
- Treino.professor_id referencia Usuario com tipo=PROFESSOR
- Inscricao.aluno_id referencia Usuario com tipo=ALUNO
- Unicidade: (treino_id, aluno_id) deve ser única
```

---
BeachBuddy — INF1407
