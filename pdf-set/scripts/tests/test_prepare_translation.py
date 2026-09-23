import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from sentence_boundaries import safe_cuts
from translation_preparation import process_text
from prepare_translation import canonical, prepare, validate_content


class SentenceTests(unittest.TestCase):
    def test_all_500_audited_boundaries(self):
        records = json.loads(Path(__file__).with_name('freud_boundaries.json').read_text(encoding='utf-8'))
        self.assertEqual(len(records), 500)
        for record in records:
            with self.subTest(case=record['id']):
                left, right = record['context'].split(' ⟂ ')
                text = left + ' ' + right
                self.assertNotIn(len(left)+1, safe_cuts(text))

    def test_indivisible_units(self):
        examples = ['p. 254', 'pp. 10–12', 'par ex., Paris', 'par. ex., Paris',
                    'p. ex., Paris', 'c.-à-d. : cela', 'c. -à-d. cela', 'e.g. Paris',
                    'i.e. Paris', 'J. M. Charcot', 'J.M. Charcot', 'É. Zola',
                    'Alfr. Adler', 'Allr. Adler', 'Emmy v. N.', 'Dr K., médecin',
                    'OCF.P, IV', 'U.S.A.', 'W.-C.', '3 fl. 65 kr.', 'oct. 1911',
                    '3.14', '1.2.1895', '1. Premier élément', '(a. Versuchungen)',
                    'un mot [!] suivi', 'un mot (?) suivi', 'l. c., p. 15',
                    'Internat. Zeitschr. f. Psychoanalyse', '![a. B](img.jpg)',
                    '[Titre. Un titre](https://example.org)', 'https://example.org/a.b']
        for text in examples:
            with self.subTest(text=text):
                self.assertEqual(safe_cuts(text), [])

    def test_real_sentence_ends_remain(self):
        for text in ['Le système Ics. Certes, ceci est différent.',
                     'Le total est 4380 cour. Et voici la suite.',
                     'Mon ami Fl. À partir de là commence le récit.',
                     'Anna O. Elle revient demain.',
                     'Le prix est 50. Il le paie.',
                     'Bonjour ! Vous voici.', '问题结束。下一句。']:
            with self.subTest(text=text):
                self.assertTrue(safe_cuts(text))

    def test_long_brackets_and_notes_can_split(self):
        sentence = 'Cette phrase donne une explication complète et autonome. '
        for opening, closing in [('(', ')'), ('[', ']'), ('【', '】')]:
            raw = opening + sentence*20 + closing
            out = process_text(raw, 100, 20)
            self.assertIn('\n\n', out)
            self.assertEqual(canonical(raw), canonical(out))
        raw = 'Texte<sup>【' + sentence*20 + '】</sup> suite.'
        out = process_text(raw, 100, 20)
        self.assertGreater(out.count('<sup>'), 1)
        validate_content(raw, out)

    def test_outer_sentence_continuation(self):
        for text in ['Il dit (Une explication.) puis continue.',
                     'Un auteur (Né en 1803.), nommé ici.',
                     'Un mot (Une note.) (précisé ici) avait ce sens.',
                     'Il demande « Pourquoi ? », puis attend.',
                     'Un mot [!] et sa suite.']:
            self.assertEqual(safe_cuts(text), [], text)

    def test_note_stays_attached(self):
        text='Une phrase.<sup>【Explication.】</sup> Une autre phrase.'
        cuts=safe_cuts(text)
        self.assertEqual(cuts, [text.index('Une autre')])

    def test_no_safe_boundary_keeps_long_text(self):
        raw=('une très longue phrase sans fin '*100).strip()
        self.assertEqual(process_text(raw, 10, 0).strip(), raw)


class WorkflowTests(unittest.TestCase):
    def test_cli_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)/'测试书'
            base.mkdir()
            source=base/'测试书.md'
            source.write_text('# Titre\n\n' + 'Une phrase complète. '*60, encoding='utf-8')
            command=[sys.executable,'-X','utf8',str(SCRIPTS/'prepare_translation.py'),'--base-dir',str(base)]
            run=subprocess.run(command, capture_output=True, encoding='utf-8', env=None)
            self.assertEqual(run.returncode, 0, run.stderr)
            output=base/'translate-typeset'/'1.md'
            before=output.read_bytes()
            run=subprocess.run(command, capture_output=True, encoding='utf-8')
            self.assertNotEqual(run.returncode, 0)
            self.assertEqual(output.read_bytes(),before)
            self.assertTrue((base/'translate-split'/'1.md').is_file())

    def test_whole_paragraph_file_grouping_and_sup(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            source=base/'book.md'
            raw='A'*150+'<sup>【First.\n\nSecond.】</sup>\n\nNext.'
            source.write_text(raw,encoding='utf-8')
            result=prepare(source,base/'split',base/'typeset',file_chars=30)
            self.assertEqual(len(result),2)
            self.assertIn('Second.',result[0][0])
            self.assertEqual(canonical(raw),canonical(''.join(r[1] for r in result)))

    def test_invalid_input_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            source=base/'book.md'
            source.write_text('a<sup>broken',encoding='utf-8')
            with self.assertRaises(ValueError):
                prepare(source,base/'split',base/'typeset')
            self.assertFalse((base/'typeset').exists())


if __name__ == '__main__':
    unittest.main()
