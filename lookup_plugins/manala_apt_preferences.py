from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.lookup import LookupBase
from ansible.module_utils.six import string_types
from ansible.errors import AnsibleError
from ansible.module_utils._text import to_text

import os
import re


class LookupModule(LookupBase):

    def _recursive_flatten(self, terms):
        if not isinstance(terms, list):
            raise AnsibleError('Expect a list but was a %s' % type(terms))
        ret = []
        for term in terms:
            if isinstance(term, (list, tuple)):
                ret.extend(
                    self._recursive_flatten(term)
                )
            else:
                ret.append(term)
        return ret

    def run(self, terms, variables=None, **kwargs):

        results = []

        wantstate = kwargs.pop('wantstate', None)

        if wantstate and wantstate not in ['present', 'absent']:
            raise AnsibleError('Expect a wanstate of "present" or "absent" but was "%s"' % to_text(wantstate))

        preferences = self._recursive_flatten(terms[0])
        preferencesPatterns = terms[1]
        repositoriesPatterns = terms[2]
        exclusives = self._flatten(terms[3])
        dir = terms[4]
        template = terms[5]

        itemDefault = {
            'state': 'present',
            'template': template
        }

        # Mark exclusive preferences as absent
        for preference in exclusives:
            item = itemDefault.copy()
            item.update({
                'file': preference['path'],
                'state': 'absent'
            })
            results.append(item)

        for preference in preferences:

            items = []

            item = itemDefault.copy()

            # Short syntax
            if isinstance(preference, string_types):
                item.update({
                    'preference': preference
                })
            else:
                # Must be a dict
                if not isinstance(preference, dict):
                    raise AnsibleError('Expect a dict but was a %s' % type(preference))

                item.update(preference)

                if item['state'] not in ['present', 'absent', 'ignore']:
                    raise AnsibleError('Expect a state of "present", "absent" or "ignore" but was "%s"' % to_text(item['state']))

                if item['state'] == 'ignore':
                    continue

            if 'preference' in item:
                pattern = item['preference']
                preferencePattern = pattern.split('@')[0]
                if 'file' not in item:
                    item.update({
                        'file': preferencePattern
                            .split(':')[0]
                            .replace('.', '_')
                    })
                if 'package' not in item:
                    item.update({
                        'package': preferencesPatterns.get(
                            preferencePattern,
                            (preferencePattern)
                                if len(pattern.split('@')) > 1 else
                            ('*')
                        )
                    })
                if 'pin' not in item:
                    repositoryPattern = (
                            (pattern.split('@')[1])
                                if len(pattern.split('@')) > 1 else
                            (pattern)
                        ).split(':')[0]
                    if repositoryPattern not in repositoriesPatterns:
                        raise AnsibleError('unable to find "%s" repository pattern' % repositoryPattern)
                    item.update({
                        'pin': repositoriesPatterns
                            .get(repositoryPattern)
                            .get(
                                'pin',
                                'origin ' + re.sub(
                                    'deb (\\[.+\\] )?https?:\\/\\/([^\\/ ]+)[\\/ ].*$',
                                    '\\2',
                                    repositoriesPatterns
                                        .get(repositoryPattern)
                                        .get('source')
                                )
                            ),
                        'repository': repositoryPattern
                    })
                if 'priority' not in item:
                    item.update({
                        'priority': int(
                            (pattern.split(':')[1])
                                if len(pattern.split(':')) > 1 else
                            (900)
                        )
                    })

            # Check index key
            if 'file' not in item:
                raise AnsibleError('Expect "file" key')

            item.update({
                'file': os.path.join(dir, item['file'])
            })

            items.append(item)

            # Merge by index key
            for item in items:
                itemFound = False
                for i, result in enumerate(results):
                    if result['file'] == item['file']:
                        results[i] = item
                        itemFound = True
                        break

                if not itemFound:
                    results.append(item)

        # Filter by state
        if wantstate:
            results = [result for result in results if result.get('state') == wantstate]

        return results
