1. Quais foram as principais decisões técnicas adotadas durante o desenvolvimento?
FastAPI + SQLite, Detecção de conflitos de horários via SQL, Autenticação simples por API KEY, testes com pytest e TestCliente

2. Se tivesse mais tempo, o que você implementaria ou melhoraria?
Cache com expiração configurável (hoje o cache de salas nunca expira sozinho).
Adicionar suporte a PostgreSQL via Docker Compose, facilitando ainda mais a execução.
Mais testes de borda (ex: reservas que terminam exatamente quando outra começa).

3. Você utilizou alguma ferramenta de IA durante o desenvolvimento?
Sim, utilizei o Claude durante o desenvolvimento de Ajudar a implementar e depurar autenticação, cache, logs e ordenação, incluindo a correção, Estruturar o projeto e organizar a separação entre modelos, validação e regras de negócios.