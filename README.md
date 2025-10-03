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

## 4. Fluxos do Usuário
### Fluxo: Cadastro Aluno e Inscrição em Treino
1. Acessa /signup/aluno/.
2. Após login é redirecionado para “Meus Treinos”.
3. Clica em “Novo Treino”.
4. Escolhe um CT (lista paginada simples por nome).
5. Visualiza treinos futuros do CT (exibe modalidade, data, horários, vagas restantes, professor).
6. Clica em “Inscrever-me” se houver vaga → volta para “Meus Treinos”.

### Fluxo: Professor gerenciando treinos
1. Faz login como professor.
2. Dashboard lista treinos futuros (ordenados) + métricas.
3. Abre modal “Novo Treino”, seleciona CT, preenche horários.
4. Se houver conflito é exibida mensagem de erro no modal.
5. Pode editar ou excluir treinos existentes também via modal.

### Fluxo: Gerente cadastrando CT
1. Faz login como gerente.
2. Vai para “Meus CTs”.
3. Clica em “Novo CT”, preenche dados e salva.
4. Entra em “Gerenciar Professores” para vincular professores existentes.
5. Professores vinculados passam a poder criar treinos para aquele CT.

## 5. Tecnologias e Dependências
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

Front-end:
- HTML + Django Template Language.
- CSS customizado (grid responsivo, componentes de card, badges, header fixo).

Não foram usados frameworks JS pesados para manter simplicidade do MVP.

## 6. Estrutura de Pastas 
```
ct_praia/
  main/
    models.py, views.py, forms.py, decorators.py, mixins.py
    templates/ (base + aluno/ professor/ gerente/ ct/ perfil/ registration/)
    static/ css/style.css images/
  manage.py
requirements.txt
Procfile (suporte a deploy)
runtime.txt (versão Python para plataformas compatíveis)
```


## 8. O que Funciona Bem
- Cadastro e login dos usuarios.
- Regras de capacidade e prevenção de overbooking.
- Bloqueio de conflito de horário para professores.
- Associação professor–CT garante integridade operacional.

## 9. O que não funcionou
- Ao se inscrever, o aluno vê 1/10 vagas(exemplo), esse 1 era para ser o que resta de vagas, mas é quantos alunos estão inscritos.
- Ao ver todos os treinos de um CT ao clicar Cts_> agenda completa, o botão de se inscrever está disponível para treinos que já passaram, apesar que conseguimos filtrar pra em Meus treinos só aparecerem os próximos
- Tecnicamente o professor não poderia criar um treino em uma data antiga, e está podendo.

## 10. Limitações / Próximos Passos
- Não há grandes implementações de seguranca no site, importante para producao
- Filtrar localidade, dia e esporte.

## 11. Como Executar Localmente
# Tem que comentar algumas coisas allowed_hosts e csrf_trusted_origins da producao e descomentar a do local.
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

O site está hospedado pelo Heroku e está no dominio beachbuddy.com.br caso não queira rodar localmente.




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
