import type { ReactNode } from 'react';
import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './styles.module.css';
import Link from "@docusaurus/Link";

type FeatureItem = {
  title: React.ReactNode; // Changed to ReactNode to allow links
  Svg: React.ComponentType<React.ComponentProps<'svg'>>;
  description: ReactNode;
};

const FeatureList: FeatureItem[] = [
  /* {
     title: (
       <Link to="/utfpr/ELT72B/intro">
         Sistemas Digitais
       </Link>
     ),
     Svg: require('@site/static/img/office-svgrepo-com.svg').default,
     description: (
       <>
         A disciplina de sistemas digitais é gerenciada via {" "}
         <a href="https://moodle.utfpr.edu.br/course/view.php?id=27864" target="_blank">
           Moodle
         </a>, o <Link to="/ead/intro">EaD</Link> com videoaulas e questionários. O conteúdo é disponibilizado no{" "}<a href="https://moodle.utfpr.edu.br/course/view.php?id=27864" target="_blank">
           Moodle
         </a>{" "}e as atividades são realizadas de forma assíncrona, permitindo que os alunos possam acessar o conteúdo e realizar as atividades no seu próprio ritmo.
 
         Ministrada via{" "}
         <a href="https://moodle.utfpr.edu.br/course/view.php?id=27864" target="_blank">
           Moodle
         </a>{" "}!
       </>
     ),
   }, */
  {
    title: (
      <Link to="/ead/intro">
        Ensino a Distância
      </Link>
    ),
    Svg: require('@site/static/img/online-seminar-svgrepo-com.svg').default,
    description: (
      <>
        As atividades de <Link to="/ead/intro">ensino a distância</Link> constituem em uma sequencia de videoaulas explicativas acompanhadas de questionários. As atividades são realizadas de forma assíncrona, permitindo que os alunos possam acessar o conteúdo e realizar as atividades no seu próprio ritmo.
      </>
    ),
  },
  {
    title: (
      <Link to="/lab/intro">
        Laboratório
      </Link>
    ),
    Svg: require('@site/static/img/lab-medical-test-svgrepo-com.svg').default,
    description: (
      <>
        As atividades de <Link to="/lab/intro">laboratório</Link> constituem da aplicação prática dos conteúdos vistos no <Link to="/ead/intro">ensino a distância</Link>. As atividades são realizadas de forma síncrona, com encontros semanais para a realização das atividades práticas, promovendo a interação entre os alunos e a aplicação dos conceitos vistos.
      </>
    ),
  },
  {
    title: (
      <Link to="/pjts/intro">
        Projeto Final
      </Link>
    ),
    Svg: require('@site/static/img/project-svgrepo-com.svg').default,
    description: (
      <>
        O <Link to="/pjts/intro">projeto final</Link> constitue em aplicar os conhecimentos adquiridos ao longo do curso para desenvolver um protótipo utilizando o  <a href="https://www.arduino.cc/" target="_blank">Arduino</a>. O projeto é desenvolvido em grupos, promovendo a colaboração entre os alunos e a aplicação prática dos conceitos aprendidos.
      </>
    ),
  },

];

function Feature({ title, Svg, description }: FeatureItem) {
  return (
    <div className={clsx('col col--4')}>
      <div className="text--center">
        <Svg className={styles.featureSvg} role="img" />
      </div>
      <div className="text--center padding-horiz--md">
        <Heading as="h3">{title}</Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures(): ReactNode {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
