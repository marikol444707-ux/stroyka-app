import {createClientForm, createProjectForm} from './projectInitialForms';

test('new project starts without an exact customer selection', () => {
  expect(createProjectForm()).toMatchObject({clientId:null, client:''});
});

test('customer card carries legal and signer fields needed by contracts', () => {
  expect(createClientForm()).toMatchObject({
    inn:'', kpp:'', ogrn:'', legalAddress:'',
    directorName:'', directorPosition:'', basis:'',
    bankName:'', bik:'', rs:'', ks:'',
  });
});
