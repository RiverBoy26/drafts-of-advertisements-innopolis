// Демонстрационный анализ текста. В продакшене заменяется вызовом Spring Boot API,
// который может делегировать извлечение услуг и классификацию Python ML сервису.
const taxonomy = [
  { key: 'Укладка плитки', tests: [/плитк|кафел|керамогранит/i], category: 'Ремонт и отделка', microcategory: 'Укладка плитки', title: 'Укладка плитки в ванной и на кухне', description: 'Выполняю работы по укладке плитки в ванной комнате, на кухне и в других помещениях. Детали работы и объём обсуждаются индивидуально.' },
  { key: 'Поклейка обоев', tests: [/обо(и|ев|ями)|оклейк/i], category: 'Ремонт и отделка', microcategory: 'Поклейка обоев', title: 'Поклейка обоев в квартире', description: 'Выполняю поклейку обоев в жилых помещениях. Уточню детали и объём работ перед началом.' },
  { key: 'Установка дверей', tests: [/двер|дверн/i], category: 'Ремонт и отделка', microcategory: 'Установка дверей', title: 'Установка межкомнатных дверей', description: 'Выполняю работы по установке дверей. Обсудим особенности помещения и объём работ.' },
  { key: 'Электромонтаж', tests: [/электр|проводк|розетк|освещени/i], category: 'Ремонт и отделка', microcategory: 'Электромонтажные работы', title: 'Электромонтажные работы', description: 'Выполняю электромонтажные работы. Уточняю перечень и условия работ индивидуально.' },
  { key: 'Сантехнические работы', tests: [/сантех|унитаз|раковин|смесител|труб/i], category: 'Ремонт и отделка', microcategory: 'Сантехнические работы', title: 'Установка и ремонт сантехники', description: 'Выполняю сантехнические работы. Объём и особенности задачи обсуждаются индивидуально.' },
  { key: 'Монтаж гипсокартона', tests: [/гипсокартон|гкл/i], category: 'Ремонт и отделка', microcategory: 'Монтаж гипсокартона', title: 'Монтаж гипсокартона', description: 'Выполняю работы по монтажу гипсокартона. Детали и объём работ обсуждаются перед началом.' },
  { key: 'Ремонт квартир', tests: [/ремонт квартир|ремонт под ключ|отделк квартир/i], category: 'Ремонт и отделка', microcategory: 'Ремонт квартир', title: 'Ремонт квартир', description: 'Выполняю работы по ремонту квартир. Состав работ и условия обсуждаются индивидуально.' },
];
export const categoryChoices = ['Ремонт квартир', 'Укладка плитки', 'Поклейка обоев', 'Установка дверей', 'Электромонтажные работы', 'Сантехнические работы', 'Монтаж гипсокартона', 'Другая услуга'];
export const exampleText = 'Выполняю ремонт квартир под ключ. Занимаюсь укладкой плитки, поклейкой обоев, монтажом гипсокартона, установкой дверей и электромонтажными работами. Работаю аккуратно, обсуждаю детали заранее.';
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
export async function mockAnalyze(text) {
  await wait(1000);
  const selected = taxonomy.filter(item => item.tests.some(re => re.test(text)));
  const matches = selected.length ? selected : [{key:'Услуга из описания', category:'Услуги', microcategory:'Другая услуга', title:'Услуги по вашему запросу', description:'Оказываю услуги, указанные в описании. Подробности можно обсудить индивидуально.'}];
  return matches.map((item, i) => ({ id: crypto.randomUUID(), service: item.key, category: item.category, microcategory: item.microcategory, confidence: selected.length ? (i < 3 ? 'high' : 'medium') : 'low', title: item.title, description: item.description, selected: true }));
}
export async function mockGenerate(services) {
  await wait(750);
  return services.map(s => ({ id: crypto.randomUUID(), service: s.service, category: s.category, microcategory: s.microcategory, title: s.title || s.service, description: s.description || `Выполняю работы: ${s.service.toLowerCase()}. Детали обсуждаются индивидуально.`, status:'Черновик', createdAt: new Date().toISOString() }));
}
