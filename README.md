# BeachBuddy
Projeto para INF1407 

## ERD (ASCII)

```text
+---------------------------+
|          Usuario          |
+---------------------------+
| id (PK)                   |  (n)         
| tipo: {ALUNO, PROFESSOR,  |---------------------------|
|        GERENTE?}          |                           |
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

...existing