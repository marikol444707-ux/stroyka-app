"""Real manager reassignment/revocation browser scenario for the local runner."""
from urllib.parse import urlsplit


def browser_check(state, artifacts, chromium):
    from playwright.sync_api import sync_playwright, expect
    row = state['managerScenario']

    def login(page, actor):
        page.goto('http://localhost:8001/app')
        page.locator('input[type=email]').fill(state['users'][actor]['email'])
        page.locator('input[type=password]').fill(state['password'])
        page.get_by_role('button', name='Войти в систему').click()
        page.get_by_role('navigation', name='Кабинет поставщика').wait_for()

    def offers(page):
        return page.evaluate("""async()=>{const r=await fetch('/supplier-offers');
            if(!r.ok)throw Error('Offer read '+r.status);return (await r.json()).map(o=>o.id);}""")

    def draft(page):
        page.get_by_role('button', name='Открыть заявку №'+str(row['requestA']), exact=True).click()
        page.get_by_role('button', name='Отправить КП', exact=False).click()
        page.locator('input[type=number]').nth(0).fill('101')
        page.locator('input[type=number]').nth(1).fill('1')

    def denied_submit(page):
        page.once('dialog', lambda dialog: dialog.accept())
        with page.expect_response(lambda response: response.request.method == 'PUT'
                and response.url.endswith(row['path'])) as response:
            page.get_by_role('button', name='Отправить КП', exact=True).click()
        assert response.value.status == 403
        expect(page.get_by_role('alert')).to_contain_text('Не удалось отправить КП')

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=chromium, headless=True, args=['--no-sandbox'])
        try:
            for size, width, height in [('mobile', 390, 844), ('desktop', 1280, 900)]:
                contexts = [browser.new_context(viewport={'width': width, 'height': height}) for _ in range(3)]
                errors, server_errors = [], []
                try:
                    for context in contexts:
                        context.route('**/*', lambda route: route.continue_() if urlsplit(route.request.url).hostname
                            in ('localhost', '127.0.0.1') else route.abort())
                    owner, manager_a, manager_b = [context.new_page() for context in contexts]
                    for page in (owner, manager_a, manager_b):
                        page.set_default_timeout(15000)
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.on('response', lambda response: server_errors.append(urlsplit(response.url).path)
                            if response.status >= 500 else None)
                    login(owner, 'supplier')
                    owner.get_by_role('button', name='Заказчики', exact=False).click()
                    assignments = owner.get_by_role('region', name='Ответственные за заказчиков')
                    for company, member in [(2, row['memberA']), (3, row['memberB'])]:
                        assignments.get_by_label('Ответственный за SUPPLY CHAIN company '+str(company)).select_option(str(member))
                        expect(assignments.get_by_role('status')).to_have_text('Изменения сохранены')
                    login(manager_a, 'manager')
                    login(manager_b, 'manager_b')
                    assert offers(manager_a) == [row['offerA']]
                    assert offers(manager_b) == [row['offerB']]
                    draft(manager_a)
                    assignments.get_by_label('Ответственный за SUPPLY CHAIN company 2').select_option(str(row['memberB']))
                    expect(assignments.get_by_role('status')).to_have_text('Изменения сохранены')
                    denied_submit(manager_a)
                    manager_a.screenshot(path=str(artifacts / (size+'-reassigned-draft.png')))
                    assert offers(manager_a) == []
                    assert {row['offerA'], row['offerB']} <= set(offers(manager_b))
                    manager_b.reload()
                    draft(manager_b)
                    owner.get_by_role('button', name='Команда', exact=False).click()
                    team = owner.get_by_role('region', name='Команда поставщика')
                    member = team.locator('article').filter(has=owner.get_by_role('heading', name='TEAM second manager', exact=True))
                    owner.once('dialog', lambda dialog: dialog.accept('Синтетическая проверка отзыва доступа'))
                    member.get_by_role('button', name='Отключить менеджера').click()
                    expect(member.get_by_role('button', name='Включить менеджера')).to_be_enabled()
                    denied_submit(manager_b)
                    assert offers(manager_b) == []
                    member.get_by_role('button', name='Включить менеджера').click()
                    expect(member.get_by_role('button', name='Отключить менеджера')).to_be_enabled()
                    assert offers(manager_b) == []
                    owner.get_by_role('button', name='Заказчики', exact=False).click()
                    assignments = owner.get_by_role('region', name='Ответственные за заказчиков')
                    for company in (2, 3):
                        expect(assignments.get_by_label('Ответственный за SUPPLY CHAIN company '+str(company))).to_have_value('')
                    assert {row['offerA'], row['offerB']} <= set(offers(owner))
                    assert not errors, errors
                    assert not server_errors, server_errors
                    print(size+': separate buyers, reassignment/disable reject open drafts, reenable restores no assignments', flush=True)
                finally:
                    for context in contexts:
                        context.close()
        finally:
            browser.close()
