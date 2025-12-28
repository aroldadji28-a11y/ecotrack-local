from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from .models import Depense
from .views import _normalize_input


class DepenseFreeQuartierTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_create_depense_with_free_quartier(self):
        data = {
            'type_depense': 'alimentation',
            'quartier': 'Quartier Libre Test',
            'prix': '250.00',
            'lieu': 'Test lieu',
            'date': timezone.now().date().isoformat(),
        }
        resp = self.client.post(reverse('saisie'), data, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Depense.objects.filter(quartier='Quartier Libre Test').exists())

    def test_comparaison_accepts_free_quartier(self):
        Depense.objects.create(type_depense='alimentation', quartier='qfree1', prix=100, lieu='L', date=timezone.now().date())
        Depense.objects.create(type_depense='alimentation', quartier='QFree2', prix=200, lieu='L', date=timezone.now().date())
        # Query with variant casing/spaces; normalization should match stored values
        resp = self.client.get(reverse('comparaison'), {'q1': ' QFree1 ', 'q2': 'qfree2 '})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Qfree1')
        self.assertContains(resp, 'Qfree2')

    def test_quartier_normalization_on_save(self):
        dep = Depense.objects.create(type_depense='alimentation', quartier='  centre-ville  ', prix=50, lieu='L', date=timezone.now().date())
        self.assertEqual(dep.quartier, 'Centre Ville')

    def test_export_csv_filters(self):
        # Create sample data across months and prices
        d1 = Depense.objects.create(type_depense='alimentation', quartier='Q1', prix=100, lieu='L1', date=timezone.now().date())
        d2 = Depense.objects.create(type_depense='logement', quartier='Q2', prix=500, lieu='L2', date=timezone.now().date())
        # Different month
        d3 = Depense.objects.create(type_depense='transport', quartier='Q1', prix=200, lieu='L3', date=timezone.now().date())

        # Filter by quartier
        resp = self.client.get(reverse('export_csv'), {'quartier': ' q1 '})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv')
        content = resp.content.decode('utf-8')
        self.assertIn('date,type,quartier,lieu,prix,commentaire,anomalie', content)
        # Should contain Q1 rows but not Q2
        self.assertIn('Q1', content)
        self.assertNotIn('Q2', content)

    def test_export_anomalies_csv(self):
        dep = Depense.objects.create(type_depense='alimentation', quartier='QX', prix=1000, lieu='LX', date=timezone.now().date(), anomalie='[AUTO] Test')
        resp = self.client.get(reverse('export_anomalies_csv'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv')
        content = resp.content.decode('utf-8')
        self.assertIn('[AUTO] Test', content)

    def test_dashboard_median_calculation(self):
        # Create a set of depenses with known medians per quartier
        Depense.objects.create(type_depense='alimentation', quartier='M1', prix=100, lieu='L', date=timezone.now().date())
        Depense.objects.create(type_depense='alimentation', quartier='M1', prix=200, lieu='L', date=timezone.now().date())
        Depense.objects.create(type_depense='alimentation', quartier='M1', prix=300, lieu='L', date=timezone.now().date())
        # Median for M1 should be 200
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        stats = resp.context['stats_quartier']
        m1 = next((s for s in stats if s['quartier'] == 'M1'), None)
        self.assertIsNotNone(m1)
        self.assertAlmostEqual(m1['mediane'], 200.0)

    def test_comparaison_quartier_vs_quartier(self):
        # Q1: 100,200 ; Q2: 300,400
        Depense.objects.create(type_depense='alimentation', quartier='Q1', prix=100, lieu='L', date=timezone.now().date())
        Depense.objects.create(type_depense='alimentation', quartier='q1', prix=200, lieu='L', date=timezone.now().date())
        Depense.objects.create(type_depense='alimentation', quartier='Q2', prix=300, lieu='L', date=timezone.now().date())
        Depense.objects.create(type_depense='alimentation', quartier='q2', prix=400, lieu='L', date=timezone.now().date())
        # Use variant casing/spaces in query params
        resp = self.client.get(reverse('comparaison'), {'q1': ' q1 ', 'q2': 'Q2 '})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('mode', resp.context)
        self.assertEqual(resp.context['mode'], 'quartier_vs_quartier')
        self.assertIn('stats_q1', resp.context)
        self.assertIn('stats_q2', resp.context)
        self.assertAlmostEqual(resp.context['stats_q1']['mediane'], 150.0)
        self.assertAlmostEqual(resp.context['stats_q2']['mediane'], 350.0)

    def test_comparaison_quartier_ville(self):
        Depense.objects.create(type_depense='alimentation', quartier='QV', prix=50, lieu='L', date=timezone.now().date())
        Depense.objects.create(type_depense='alimentation', quartier='QV', prix=150, lieu='L', date=timezone.now().date())
        # global entries
        Depense.objects.create(type_depense='alimentation', quartier='X', prix=200, lieu='L', date=timezone.now().date())
        resp = self.client.get(reverse('comparaison'), {'mode': 'quartier_ville', 'quartier': ' qv '})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context.get('mode'), 'quartier_vs_ville')
        self.assertIn('stats_quartier', resp.context)
        self.assertAlmostEqual(resp.context['stats_quartier']['mediane'], 100.0)

    def test_comparaison_campus_v_env(self):
        Depense.objects.create(type_depense='alimentation', quartier='campus', prix=80, lieu='L', date=timezone.now().date())
        Depense.objects.create(type_depense='alimentation', quartier='campus', prix=120, lieu='L', date=timezone.now().date())
        Depense.objects.create(type_depense='alimentation', quartier='autre', prix=200, lieu='L', date=timezone.now().date())
        resp = self.client.get(reverse('comparaison'), {'mode': 'campus_env'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context.get('mode'), 'campus_vs_env')
        self.assertIn('stats_campus', resp.context)
        self.assertIn('stats_env', resp.context)

    def test_export_comparaison_csv_quartier_vs_quartier(self):
        d1 = Depense.objects.create(type_depense='alimentation', quartier='QX', prix=100, lieu='L1', date=timezone.now().date())
        d2 = Depense.objects.create(type_depense='alimentation', quartier='QY', prix=200, lieu='L2', date=timezone.now().date())
        resp = self.client.get(reverse('export_comparaison_csv'), {'q1': ' qx ', 'q2': ' qy '})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv')
        content = resp.content.decode('utf-8')
        lines = [l for l in content.splitlines() if l.strip()]
        # header
        self.assertEqual(lines[0], 'groupe,date,type,quartier,lieu,prix,commentaire,anomalie')
        rows = lines[1:]
        # Exactly one row per created depense and groups labelled q1/q2
        self.assertEqual(sum(1 for r in rows if r.startswith('q1,')), 1)
        self.assertEqual(sum(1 for r in rows if r.startswith('q2,')), 1)
        # Ensure the quartier column holds the normalized quartier string
        expected_q1 = _normalize_input(' qx ')
        expected_q2 = _normalize_input(' qy ')
        self.assertTrue(any(r.startswith('q1,') and r.split(',')[3] == expected_q1 for r in rows))
        self.assertTrue(any(r.startswith('q2,') and r.split(',')[3] == expected_q2 for r in rows))

    def test_export_comparaison_csv_campus_env(self):
        Depense.objects.create(type_depense='alimentation', quartier='campus', prix=50, lieu='Lc', date=timezone.now().date())
        Depense.objects.create(type_depense='alimentation', quartier='campus', prix=75, lieu='Lc2', date=timezone.now().date())
        Depense.objects.create(type_depense='alimentation', quartier='autre', prix=150, lieu='Le', date=timezone.now().date())
        resp = self.client.get(reverse('export_comparaison_csv'), {'mode': 'campus_env'})
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        lines = [l for l in content.splitlines() if l.strip()]
        self.assertEqual(lines[0], 'groupe,date,type,quartier,lieu,prix,commentaire,anomalie')
        rows = lines[1:]
        self.assertTrue(any(r.startswith('campus,') for r in rows))
        self.assertTrue(any(r.startswith('environnement,') for r in rows))
        # Number of campus rows should match created campus depenses (2)
        self.assertEqual(sum(1 for r in rows if r.startswith('campus,')), 2)
        # Also accept explicit campus parameter with variant spacing/casing
        resp2 = self.client.get(reverse('export_comparaison_csv'), {'mode': 'campus_env', 'campus': ' campus '})
        self.assertEqual(resp2.status_code, 200)
        content2 = resp2.content.decode('utf-8')
        lines2 = [l for l in content2.splitlines() if l.strip()]
        rows2 = lines2[1:]
        self.assertEqual(sum(1 for r in rows2 if r.startswith('campus,')), 2)

    def test_export_comparaison_csv_quartier_vs_ville(self):
        Depense.objects.create(type_depense='alimentation', quartier='QV', prix=50, lieu='L1', date=timezone.now().date())
        Depense.objects.create(type_depense='alimentation', quartier='QV', prix=150, lieu='L2', date=timezone.now().date())
        # global entries
        Depense.objects.create(type_depense='alimentation', quartier='X', prix=200, lieu='L3', date=timezone.now().date())
        resp = self.client.get(reverse('export_comparaison_csv'), {'mode': 'quartier_ville', 'quartier': ' qv '})
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        lines = [l for l in content.splitlines() if l.strip()]
        self.assertEqual(lines[0], 'groupe,date,type,quartier,lieu,prix,commentaire,anomalie')
        rows = lines[1:]
        # Should contain 'quartier' rows and 'ville' rows
        self.assertTrue(any(r.startswith('quartier,') for r in rows))
        self.assertTrue(any(r.startswith('ville,') for r in rows))
