import unittest
from mock import patch
from dzclient import DatazillaRequest, DatazillaResult, DatazillaResultsCollection


class DatazillaRequestTest(unittest.TestCase):
    def test_init_with_date(self):
        """Can provide test date on instantiation."""
        req = DatazillaRequest(
            'http', 'host', 'project', 'key', 'secret', test_date=12345, branch='mozilla-try')

        self.assertEqual(req.test_date, 12345)


    def test_add_datazilla_result(self):
        """Can add a DatazillaResult to a DatazillaRequest."""
        req = DatazillaRequest(
            'http', 'host', 'project', 'key', 'secret',
            branch='mozilla-try'
            )
        res = DatazillaResult({'suite': {'test': [1, 2, 3]}})

        req.add_datazilla_result(res)

        self.assertEqual(req.results.results, res.results)


    def test_add_second_datazilla_result(self):
        """Adding a second DatazillaResult joins their results."""
        req = DatazillaRequest(
            'http', 'host', 'project', 'key', 'secret',
            branch='mozilla-try'
            )
        res1 = DatazillaResult({'suite1': {'test': [1]}})
        res2 = DatazillaResult({'suite2': {'test': [2]}})

        req.add_datazilla_result(res1)
        req.add_datazilla_result(res2)

        self.assertEqual(
            req.results.results,
            {'suite1': {'test': [1]}, 'suite2': {'test': [2]}},
            )

    def test_create_from_results_collection(self):
        collection = DatazillaResultsCollection(machine_name='localhost',
                                                os='linux',
                                                branch='mozilla-try')
        test_date = collection.test_date
        req = DatazillaRequest.create(
            'http', 'host', 'project', 'key', 'secret', collection
            )
        self.assertEqual(req.machine_name, 'localhost')
        self.assertEqual(req.os, 'linux')
        self.assertEqual(req.test_date, test_date)
        self.assertEqual(req.host, 'host')
        self.assertEqual(req.project, 'project')
        self.assertEqual(req.oauth_key, 'key')
        self.assertEqual(req.oauth_secret, 'secret')

    def test_datasets(self):
        """Tests dataset creation for submission to datazilla"""

        req = DatazillaRequest(
            protocol='http',
            host='host',
            project='project',
            oauth_key='key',
            oauth_secret='secret',
            machine_name='qm-pxp01',
            os='linux',
            os_version='Ubuntu 11.10',
            platform='x86_64',
            build_name='Firefox',
            version='14.0a2',
            revision='785345035a3b',
            branch='Mozilla-Aurora',
            id='20120228122102',
            )

        results = {'suite1': {'test1': [1]}, 'suite2': {'test2': [2]}}
        req.add_datazilla_result(DatazillaResult(results))

        datasets = req.datasets()

        self.assertEqual(len(datasets), 2)

        for dataset in datasets:
            self.assertEqual(set(dataset.keys()), set(['results', 'test_build', 'test_machine', 'testrun']))
            self.assertEqual(dataset['test_build'],
                             {'branch': 'Mozilla-Aurora',
                              'id': '20120228122102',
                              'name': 'Firefox',
                              'revision': '785345035a3b',
                              'version': '14.0a2'})
            self.assertEqual(dataset['test_machine'],
                             {'name': 'qm-pxp01',
                              'os': 'linux',
                              'osversion': 'Ubuntu 11.10',
                              'platform': 'x86_64'})
            self.assertEqual(set(dataset['testrun'].keys()), set(['suite', 'date']))
            suite = dataset['testrun']['suite']
            self.assertTrue(suite in results)
            self.assertEqual(dataset['results'], results[suite])

    @patch.object(DatazillaRequest, 'send')
    def test_submit(self, mock_send):
        """Submits blob of JSON data for each test suite."""
        req = DatazillaRequest(
            protocol='http',
            host='host',
            project='project',
            oauth_key='key',
            oauth_secret='secret',
            machine_name='qm-pxp01',
            os='linux',
            os_version='Ubuntu 11.10',
            platform='x86_64',
            build_name='Firefox',
            version='14.0a2',
            revision='785345035a3b',
            branch='Mozilla-Aurora',
            id='20120228122102',
            )

        req.add_datazilla_result(
            DatazillaResult(
                {'suite1': {'test1': [1]}, 'suite2': {'test2': [2]}}
                )
            )

        req.submit()

        self.assertEqual(mock_send.call_count, 2)
        data1 = mock_send.call_args_list[0][0][0]
        data2 = mock_send.call_args_list[1][0][0]

        results = sorted([data1.pop('results'), data2.pop('results')])

        self.assertEqual(results, sorted([{'test1': [1]}, {'test2': [2]}]))

        suites = sorted(
            [data1['testrun'].pop('suite'), data2['testrun'].pop('suite')])

        self.assertEqual(suites, sorted(['suite1', 'suite2']))

        # aside from results and suite, datasets are the same
        self.assertEqual(data1, data2)

        self.assertEqual(
            data1['test_build'],
            {
                'branch': 'Mozilla-Aurora',
                'id': '20120228122102',
                'name': 'Firefox',
                'revision': '785345035a3b',
                'version': '14.0a2',
                },
            )

        self.assertEqual(
            data1['test_machine'],
            {
                'name': 'qm-pxp01',
                'os': 'linux',
                'osversion': 'Ubuntu 11.10',
                'platform': 'x86_64',
                },
            )

        self.assertEqual(data1['testrun']['date'], req.test_date)


    @patch("dzclient.client.oauth.generate_nonce")
    @patch("dzclient.client.oauth.time.time")
    @patch("dzclient.client.httplib.HTTPConnection")
    def test_send(self,
                  mock_HTTPConnection, mock_time, mock_generate_nonce):
        """Can send data to the server."""
        mock_time.return_value = 1342229050
        mock_generate_nonce.return_value = "46810593"

        protocol = 'http'
        host = "datazilla.mozilla.org"
        project = "project"
        key = "oauth-key"
        secret = "oauth-secret"
        req = DatazillaRequest(protocol, host, project, key, secret, branch='mozilla-try')

        mock_conn = mock_HTTPConnection.return_value
        mock_request = mock_conn.request
        mock_response = mock_conn.getresponse.return_value

        response = req.send({"some": "data"})

        self.assertEqual(mock_HTTPConnection.call_count, 1)
        self.assertEqual(mock_HTTPConnection.call_args[0][0], host)

        self.assertEqual(mock_response, response)

        self.assertEqual(mock_request.call_count, 1)

        method, path, data, header = mock_request.call_args[0]
        self.assertEqual(method, "POST")
        self.assertEqual(path, "/project/api/load_test")
        self.assertEqual(data, 'oauth_body_hash=2jmj7l5rSw0yVb%2FvlWAYkK%2FYBwk%3D&oauth_nonce=46810593&oauth_timestamp=1342229050&oauth_consumer_key=oauth-key&oauth_signature_method=HMAC-SHA1&oauth_version=1.0&oauth_token=&user=project&oauth_signature=mKpovMfgWJqlcVKSdcTCbw4gfaM%3D&data=%257B%2522some%2522%253A%2520%2522data%2522%257D')

        self.assertEqual(
            header['Content-type'],
            'application/x-www-form-urlencoded',
            )

    @patch("dzclient.client.httplib.HTTPConnection")
    def test_send_without_oauth(self, mock_HTTPConnection):
        """Can send data to the server without oauth"""

        protocol = 'http'
        host = "datazilla.mozilla.org"
        project = "project"
        key = None
        secret = None
        req = DatazillaRequest(protocol, host, project, key, secret, branch='mozilla-try')

        mock_conn = mock_HTTPConnection.return_value
        mock_request = mock_conn.request
        mock_response = mock_conn.getresponse.return_value

        response = req.send({"some": "data"})

        self.assertEqual(mock_HTTPConnection.call_count, 1)
        self.assertEqual(mock_HTTPConnection.call_args[0][0], host)

        self.assertEqual(mock_response, response)

        self.assertEqual(mock_request.call_count, 1)

        method, path, data, header = mock_request.call_args[0]
        self.assertEqual(method, "POST")
        self.assertEqual(path, "/project/api/load_test")
        self.assertEqual(data, 'data=%257B%2522some%2522%253A%2520%2522data%2522%257D')

        self.assertEqual(
            header['Content-type'],
            'application/x-www-form-urlencoded',
            )


if __name__ == '__main__':
    unittest.main()
