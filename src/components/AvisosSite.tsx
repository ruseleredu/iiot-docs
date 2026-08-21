
import React from 'react';
// import Tabs from "@theme/Tabs";
// import TabItem from "@theme/TabItem";
// import ThemeCodeBlock from '@theme/CodeBlock';
import Admonition from '@theme/Admonition';
// import Details from '@theme/Details';

// import { LABsIncomplete, EaDIncomplete } from '@site/src/components/AvisosSite';

// import {LABsIncomplete} from '@site/src/components/AvisosSite';
// <LABsIncomplete />
export function LABsIncomplete() {
    return (
        <>
            <Admonition type="warning" title="Atividade em Construção">
                <p>A documentação desta atividade de laboratório está em <b>processo de construção</b> e por isso pode estar incompleta.</p>
                <p>Utilize como base a descrição apresentada no <a href="https://moodle.utfpr.edu.br/course/view.php?id=35058">Moodle da disciplina</a>.</p>
            </Admonition>
        </>
    );
}

// import {LABsApoio} from '@site/src/components/AvisosSite';
// <LABsApoio />
export function LABsApoio() {
    return (
        <>
            <Admonition type="info" title="Documentação de Apoio para Atividade de Laboratório">
                <p>A documentação desta atividade de laboratório é <b>complementar</b> a documentação principal da disciplina.</p>
                <p>Utilize como base a descrição apresentada no <a href="https://moodle.utfpr.edu.br/course/view.php?id=35058">Moodle da disciplina</a>.</p>
            </Admonition>
        </>
    );
}

// import {EaDIncomplete} from '@site/src/components/AvisosSite';
// <EaDIncomplete />
export function EaDIncomplete() {
    return (
        <>
            <Admonition type="warning" title="Atividade de EaD em Construção">
                <p>A documentação desta atividade de EaD está em <b>processo de construção</b> e por isso pode estar incompleta.</p>
                <p>Utilize como base a descrição apresentada no <a href="https://moodle.utfpr.edu.br/course/view.php?id=35058">Moodle da disciplina</a>.</p>
            </Admonition>
        </>
    );
}

