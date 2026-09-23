// src/components/ConventionalCommitsTypes.jsx
import React from 'react';
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import ThemeCodeBlock from '@theme/CodeBlock';

/**
 * Componente reutilizável: Classificação dos Tipos de Conventional Commits
 * Especialmente útil para documentação de laboratórios de firmware / sistemas embarcados
 * (PlatformIO + VS Code + Wokwi / ESP32)
 *
 * Uso em qualquer arquivo .mdx:
 *
 * import ConventionalCommitsTypes from '@site/src/components/ConventionalCommitsTypes';
 *
 * <ConventionalCommitsTypes />
 */
export default function ConventionalCommitsTypes() {
    return (
        <>
            <p>
                Utilize as abas abaixo para consultar cada tipo de commit, sua finalidade,
                exemplos de uso em laboratório e os comandos correspondentes.
            </p>

            <Tabs groupId="commit-types">
                {/* ==================== feat ==================== */}
                <TabItem value="feat" label="feat" default>
                    <h3><code>feat</code> — Nova funcionalidade</h3>
                    <p><strong>Quando usar:</strong> Adicionar uma nova funcionalidade ao firmware.</p>
                    <p><strong>Contexto de laboratório:</strong> Implementar leitura de sensor, controle de atuador, conexão Wi-Fi, etc.</p>

                    <h4>Exemplos</h4>
                    <ThemeCodeBlock language="bash">
                        {`git commit -m "feat(sensor): adiciona leitura do DHT22 com média móvel"`}
                    </ThemeCodeBlock>

                    <ThemeCodeBlock language="bash">
                        {`git commit -m "feat(wifi): configura conexão automática ao Wi-Fi da sala

Usa credenciais definidas em platformio.ini e tenta
reconexão a cada 10 segundos em caso de falha."`}
                    </ThemeCodeBlock>

                    <ThemeCodeBlock language="bash">
                        {`git commit -m "feat(display): implementa tela de status no OLED"`}
                    </ThemeCodeBlock>
                </TabItem>

                {/* ==================== fix ==================== */}
                <TabItem value="fix" label="fix">
                    <h3><code>fix</code> — Correção de bug</h3>
                    <p><strong>Quando usar:</strong> Corrigir um comportamento incorreto ou erro no código.</p>
                    <p><strong>Contexto de laboratório:</strong> Overflow de buffer, pinagem errada no Wokwi, conversão incorreta de valores, etc.</p>

                    <h4>Exemplos</h4>
                    <ThemeCodeBlock language="bash">
                        {`git commit -m "fix(uart): corrige overflow no buffer de recepção"`}
                    </ThemeCodeBlock>

                    <ThemeCodeBlock language="bash">
                        {`git commit -m "fix(wokwi): resolve erro de pinagem do LED no diagrama

Alinha o pino GPIO2 do ESP32 com o LED no arquivo
diagram.json do simulador."`}
                    </ThemeCodeBlock>

                    <ThemeCodeBlock language="bash">
                        {`git commit -m "fix(sensor): corrige conversão de umidade relativa"`}
                    </ThemeCodeBlock>
                </TabItem>

                {/* ==================== docs ==================== */}
                <TabItem value="docs" label="docs">
                    <h3><code>docs</code> — Documentação</h3>
                    <p><strong>Quando usar:</strong> Alterações que afetam apenas a documentação (README, comentários, diagramas, etc.).</p>
                    <p><strong>Contexto de laboratório:</strong> Atualizar instruções de montagem, documentar pinos ou flags de compilação.</p>

                    <h4>Exemplos</h4>
                    <ThemeCodeBlock language="bash">
                        {`git commit -m "docs: atualiza README com instruções de montagem no breadboard"`}
                    </ThemeCodeBlock>

                    <ThemeCodeBlock language="bash">
                        {`git commit -m "docs(platformio): documenta flags de compilação usadas no laboratório"`}
                    </ThemeCodeBlock>

                    <ThemeCodeBlock language="bash">
                        {`git commit -m "docs: adiciona diagrama de ligação do sensor DHT22"`}
                    </ThemeCodeBlock>
                </TabItem>

                {/* ==================== style ==================== */}
                <TabItem value="style" label="style">
                    <h3><code>style</code> — Formatação / estilo</h3>
                    <p><strong>Quando usar:</strong> Mudanças que não afetam a lógica (indentação, espaços, formatação).</p>
                    <p><strong>Contexto de laboratório:</strong> Aplicar <code>clang-format</code>, padronizar estilo de código da turma.</p>

                    <h4>Exemplos</h4>
                    <ThemeCodeBlock language="bash">
                        {`git commit -m "style: aplica formatação clang-format em todos os arquivos .cpp/.h"`}
                    </ThemeCodeBlock>

                    <ThemeCodeBlock language="bash">
                        {`git commit -m "style(main): ajusta indentação e remove espaços em branco extras"`}
                    </ThemeCodeBlock>
                </TabItem>

                {/* ==================== refactor ==================== */}
                <TabItem value="refactor" label="refactor">
                    <h3><code>refactor</code> — Refatoração</h3>
                    <p><strong>Quando usar:</strong> Reorganizar o código sem alterar o comportamento externo (nem bugfix nem feature).</p>
                    <p><strong>Contexto de laboratório:</strong> Separar lógica em arquivos, extrair funções, melhorar legibilidade.</p>

                    <h4>Exemplos</h4>
                    <ThemeCodeBlock language="bash">
                        {`git commit -m "refactor(display): extrai funções de desenho para oled.cpp"`}
                    </ThemeCodeBlock>

                    <ThemeCodeBlock language="bash">
                        {`git commit -m "refactor: move constantes de pinos para config.h"`}
                    </ThemeCodeBlock>

                    <ThemeCodeBlock language="bash">
                        {`git commit -m "refactor(wifi): separa lógica de conexão em módulo próprio"`}
                    </ThemeCodeBlock>
                </TabItem>

                {/* ==================== perf ==================== */}
                <TabItem value="perf" label="perf">
                    <h3><code>perf</code> — Performance</h3>
                    <p><strong>Quando usar:</strong> Melhorias de desempenho (tempo de execução, consumo de memória, etc.).</p>
                    <p><strong>Contexto de laboratório:</strong> Otimizar leituras de ADC, reduzir tempo de amostragem, economizar RAM.</p>

                    <h4>Exemplos</h4>
                    <ThemeCodeBlock language="bash">
                        {`git commit -m "perf(adc): reduz tempo de amostragem do ADC em 30%"`}
                    </ThemeCodeBlock>

                    <ThemeCodeBlock language="bash">
                        {`git commit -m "perf(sensor): implementa média móvel para reduzir ruído sem aumentar latência"`}
                    </ThemeCodeBlock>
                </TabItem>

                {/* ==================== test ==================== */}
                <TabItem value="test" label="test">
                    <h3><code>test</code> — Testes</h3>
                    <p><strong>Quando usar:</strong> Adicionar ou corrigir testes (unitários, de integração, etc.).</p>
                    <p><strong>Contexto de laboratório:</strong> Criar testes de validação de sensores, debounce, faixas de valores.</p>

                    <h4>Exemplos</h4>
                    <ThemeCodeBlock language="bash">
                        {`git commit -m "test(sensor): adiciona teste de validação de faixa de temperatura"`}
                    </ThemeCodeBlock>

                    <ThemeCodeBlock language="bash">
                        {`git commit -m "test: cria teste unitário para função de debounce"`}
                    </ThemeCodeBlock>
                </TabItem>

                {/* ==================== build ==================== */}
                <TabItem value="build" label="build">
                    <h3><code>build</code> — Sistema de build / dependências</h3>
                    <p><strong>Quando usar:</strong> Mudanças no sistema de build, <code>platformio.ini</code>, dependências ou bibliotecas.</p>
                    <p><strong>Contexto de laboratório:</strong> Atualizar plataforma, adicionar bibliotecas, alterar flags de compilação.</p>

                    <h4>Exemplos</h4>
                    <ThemeCodeBlock language="bash">
                        {`git commit -m "build: atualiza plataforma espressif32 para versão 6.5.0"`}
                    </ThemeCodeBlock>

                    <ThemeCodeBlock language="bash">
                        {`git commit -m "build(deps): adiciona biblioteca ArduinoJson 7.0.0"`}
                    </ThemeCodeBlock>

                    <ThemeCodeBlock language="bash">
                        {`git commit -m "build: configura monitor_speed = 115200 no platformio.ini"`}
                    </ThemeCodeBlock>
                </TabItem>

                {/* ==================== ci ==================== */}
                <TabItem value="ci" label="ci">
                    <h3><code>ci</code> — Integração Contínua</h3>
                    <p><strong>Quando usar:</strong> Configurações de CI/CD (GitHub Actions, GitLab CI, etc.).</p>
                    <p><strong>Contexto de laboratório:</strong> Automatizar build e testes do projeto ESP32.</p>

                    <h4>Exemplos</h4>
                    <ThemeCodeBlock language="bash">
                        {`git commit -m "ci: adiciona workflow de build no GitHub Actions"`}
                    </ThemeCodeBlock>

                    <ThemeCodeBlock language="bash">
                        {`git commit -m "ci: configura job de verificação de formatação com clang-format"`}
                    </ThemeCodeBlock>
                </TabItem>

                {/* ==================== chore ==================== */}
                <TabItem value="chore" label="chore">
                    <h3><code>chore</code> — Manutenção</h3>
                    <p><strong>Quando usar:</strong> Tarefas de manutenção que não afetam o código-fonte principal.</p>
                    <p><strong>Contexto de laboratório:</strong> Atualizar <code>.gitignore</code>, limpar arquivos temporários do Wokwi/PlatformIO.</p>

                    <h4>Exemplos</h4>
                    <ThemeCodeBlock language="bash">
                        {`git commit -m "chore: atualiza .gitignore para ignorar arquivos do PlatformIO"`}
                    </ThemeCodeBlock>

                    <ThemeCodeBlock language="bash">
                        {`git commit -m "chore(wokwi): limpa arquivos temporários gerados pela simulação"`}
                    </ThemeCodeBlock>

                    <ThemeCodeBlock language="bash">
                        {`git commit -m "chore: remove arquivos .bak e temporários do projeto"`}
                    </ThemeCodeBlock>
                </TabItem>

                {/* ==================== revert ==================== */}
                <TabItem value="revert" label="revert">
                    <h3><code>revert</code> — Reversão</h3>
                    <p><strong>Quando usar:</strong> Desfazer um commit anterior.</p>
                    <p><strong>Contexto de laboratório:</strong> Reverter alteração que quebrou a simulação no Wokwi ou o build.</p>

                    <h4>Exemplos</h4>
                    <ThemeCodeBlock language="bash">
                        {`git commit -m "revert: reverte feat(wifi): configura conexão automática

Este commit causava travamento no Wokwi quando o
Access Point da sala estava indisponível.

Refs: abc1234"`}
                    </ThemeCodeBlock>

                    <ThemeCodeBlock language="bash">
                        {`git commit -m "revert: desfaz alteração que quebrou o diagrama do Wokwi"`}
                    </ThemeCodeBlock>
                </TabItem>
            </Tabs>
        </>
    );
}
