from pathlib import Path
import configparser
import pandas as pd
import os


def import_my_config(case, base, data):
    """
    Read config.ini
    :param case: name of the config.ini section to consider
    :param base: path (as a string) of folder containing config.ini
    :param data: root path (as a string) for the working folder for corresponding case
    :return: dictionary of configuration parameters
    """
    print('Import my config ...')

    # Import config parameters
    config = configparser.ConfigParser(
        converters={'list': lambda x: [i.strip() for i in x.split(',')]}
    )

    base_path = Path(base)
    data_path = Path(data)

    config.read(base_path.joinpath(r'config.ini'))

    my_config = {
        'MAPPING': Path(config.get(case, 'MAPPING')),
        'SCREENING_KEYS': config.getlist(case, 'SCREENING_KEYS'),
        'REGIONS': config.getlist(case, 'REGIONS'),
        'CASE_ROOT': data_path.joinpath(config.get(case, 'CASE_ROOT')),
        'YEAR_LASTAV': config.getint(case, 'year_lastav'),
        'SUBS_ID_FILE_N': config.getint(case, 'SUBS_ID_FILE_N'),
        'SUBS_FIN_FILE_N': config.getint(case, 'SUBS_FIN_FILE_N'),
        'MAIN_COMPS_FIN_FILE_N': config.getint(case, 'MAIN_COMPS_FIN_FILE_N'),
        'METHODS': config.getlist(case, 'METHODS'),
        'BASE': base_path
    }

    return my_config


def create_country_map(mapping, case_root):
    """
    Create a country mapping table from reference file
    :param mapping: path to the country mapping table file
    :param case_root: path of the working folder for the use case
    :return: Nothing
    """
    print('Read country mapping table ...')

    # Read Country mapping file
    country_map = pd.read_excel(mapping.joinpath(r'mapping_Country.xlsx'),
                                sheet_name='country_map',
                                names=['country_name_iso', 'country_name_simple', 'country_2DID_iso',
                                       'country_3DID_iso',
                                       'is_OECD', 'is_IEA', 'is_MI', 'region', 'IEA_region', 'world_player'
                                       ],
                                na_values='n.a.',
                                dtype={
                                    **{col: str for col in
                                       ['country_name_iso', 'country_name_simple', 'country_2DID_iso',
                                        'country_3DID_iso', 'Region', 'IEA_region', 'world_player'
                                        ]},
                                    **{col: bool for col in ['is_OECD', 'is_IEA', 'is_MI']}
                                }
                                ).drop(columns='region')

    print('Save country mapping table ...')
    print(case_root.joinpath(r'mapping\country_table.csv'))

    # Save it as csv
    os.mkdir(case_root.joinpath(r'Mapping'))

    country_map.to_csv(case_root.joinpath(r'mapping\country_table.csv'),
                       index=False,
                       columns=['country_name_iso', 'country_name_simple', 'country_2DID_iso', 'country_3DID_iso',
                                'is_OECD', 'is_IEA', 'is_MI', 'IEA_region', 'world_player'
                                ],
                       float_format='%.10f',
                       na_rep='n.a.'
                       )


def select_main(case_root, year_lastav, regions, country_map):
    """
    Select the main companies by region (having invested the most in R&D since 2010 and corresponding together to more
    than 99% of R&D investments in the region) and consolidate a global list of unique companies
    :param case_root: path of the working folder for the use case
    :param year_lastav: most recent year to consider for R&D expenditures
    :param regions: list of regions considered to collect the input data
    :param country_map: dataframe for country mapping
    :return: analytical report
    """
    # Initialize DFs
    all_comp = pd.DataFrame()
    main_comp = pd.DataFrame()
    report = pd.DataFrame()
    i = 0

    print('Read input table ...')

    for region in regions:
        i += 1
        print(region + ' (File #' + str(i) + '/' + str(len(regions)) + ')')

        # Read input list of companies by world region
        df = pd.read_excel(case_root.joinpath(r'input\listed companies - ' + region + '.xlsx'),
                           sheet_name='Results',
                           names=['rank', 'company_name', 'bvd9', 'bvd_id', 'country_2DID_iso'] + ['rnd_y' + str(YY) for
                                                                                                   YY in
                                                                                                   range(10, 19)[::-1]],
                           na_values='n.a.',
                           dtype={
                               **{col: str for col in ['company_name', 'bvd9', 'bvd_id', 'country_2DID_iso']},
                               **{col: float for col in ['rnd_y' + str(YY) for YY in range(10, 20)]}
                           }
                           ).drop(columns='rank')

        df['y_lastav'] = year_lastav

        df['rnd_mean'] = df[['rnd_y' + str(YY) for YY in range(10, 19)]].mean(axis=1, skipna=True)

        df['rnd_y_lastav'] = df['rnd_y' + str(abs(year_lastav) % 100)]

        # Identify the top companies that constitute 99% of the R&D expenses
        start = 0.0
        count = 0

        while start < 0.99 * df['rnd_mean'].sum():
            count += 1
            start = df.nlargest(count, ['rnd_mean'])['rnd_mean'].sum()

        main_comp_region = df.nlargest(count, ['rnd_mean'])

        # main_comp_region['Region'] = region

        # Calculates main regional statistics
        region_report = pd.DataFrame({'total_bvd9': df['bvd9'].count().sum(),
                                      '<total_rnd_y10_Y18>': df['rnd_mean'].sum(),
                                      'Selected_bvd9': main_comp_region['bvd9'].count().sum(),
                                      '<Selected_rnd_y10_Y18>': main_comp_region['rnd_mean'].sum()
                                      }, index=[region])

        # Consolidate statistics and list of top R&D performers over different regions
        all_comp = all_comp.append(df)
        main_comp = main_comp.append(main_comp_region)

        report = report.append(region_report)
        report.index.name = region

    print('Clean output table ...')

    # Drop duplicates
    main_comp_clean = main_comp.drop_duplicates(subset='bvd9', keep='first')

    # Update report statistics
    region_report = pd.DataFrame({'total_bvd9': all_comp['bvd9'].count().sum(),
                                  '<total_rnd_y10_Y18>': all_comp['rnd_mean'].sum(),
                                  'Selected_bvd9': main_comp_clean['bvd9'].count().sum(),
                                  '<Selected_rnd_y10_Y18>': main_comp_clean['rnd_mean'].sum()
                                  }, index=['total'])

    report = report.append(region_report)

    print('Merging with country_map ...')

    # Merging group country_map for allocation to world player categories
    merged = pd.merge(
        main_comp_clean, country_map[['country_2DID_iso', 'country_3DID_iso', 'world_player']],
        left_on='country_2DID_iso', right_on='country_2DID_iso',
        how='left',
        suffixes=(False, False)
    )

    print('Saving main companies output file ...')

    # Save output table of selected main companies
    merged.to_csv(case_root.joinpath(r'listed companies.csv'),
                  index=False,
                  columns=['bvd9', 'bvd_id', 'company_name', 'country_3DID_iso', 'world_player',
                           'rnd_mean', 'y_lastav', 'rnd_y_lastav'],
                  float_format='%.10f',
                  na_rep='n.a.'
                  )

    return report


def load_main_comp_fin(case_root, year_lastav, main_comp_fin_file_n, select_comp):
    """
    Loads financials for main companies
    :param case_root: path of the working folder for the use case
    :param year_lastav: most recent year to consider for R&D expenditures
    :param main_comp_fin_file_n: Number of input files to consolidate
    :return: Analytical report
    """
    main_comp_fin = pd.DataFrame()
    report = pd.DataFrame()

    print('Read main companies financials input tables')

    # Read ORBIS input list for groups financials
    for number in list(range(1, main_comp_fin_file_n + 1)):
        print('File #' + str(number) + '/' + str(main_comp_fin_file_n))
        df = pd.read_excel(
            case_root.joinpath(r'input\listed companies - financials #' + str(number) + '.xlsx'),
            sheet_name='Results',
            names=['rank', 'company_name', 'bvd9', 'bvd_id', 'country_iso', 'NACE_code', 'NACE_desc', 'year_lastav']
                  + ['rnd_y_lastav', 'Emp_number', 'operating_revenue_y_lastav', 'net_sales_y_lastav']
                  + ['rnd_y' + str(YY) for YY in range(10, 20)[::-1]],
            na_values='n.a.',
            dtype={
                **{col: str for col in ['company_name', 'bvd9', 'bvd_id', 'country_iso', 'NACE_code', 'NACE_desc']},
                **{col: float for col in ['rnd_y_lastav', 'operating_revenue_y_lastav', 'net_sales_y_lastav']
                   + ['rnd_y' + str(YY) for YY in range(10, 20)]
                   }
            }
        ).drop(columns=['rank', 'country_iso', 'NACE_code', 'NACE_desc', 'year_lastav'])

        # Consolidate subsidiaries financials
        main_comp_fin = main_comp_fin.append(df)

    main_comp_fin = main_comp_fin.dropna(subset=['rnd_y' + str(YY) for YY in range(10, 20)], how='all')

    report = report.append(
        pd.DataFrame(
            {'Selected_bvd9': main_comp_fin['bvd9'].nunique(),
             'Selected_rnd_y' + str(year_lastav)[-2:]: main_comp_fin['rnd_y' + str(year_lastav)[-2:]].sum()
             }, index=['Initial']
        ))

    main_comp_fin = main_comp_fin[main_comp_fin['bvd9'].isin(select_comp['bvd9'])]

    report = report.append(pd.DataFrame(
        {'Selected_bvd9': main_comp_fin['bvd9'].nunique(),
         'Selected_rnd_y' + str(year_lastav)[-2:]: main_comp_fin['rnd_y' + str(year_lastav)[-2:]].sum()
         }, index=['Selected']
    ))

    # Save it as csv
    main_comp_fin.to_csv(case_root.joinpath(r'listed companies - financials.csv'),
                          index=False,
                          float_format='%.10f',
                          na_rep='n.a.'
                          )

    return report


def select_subs(case_root, subs_id_file_n):
    """
    Consolidate a unique list of subsidiaries
    :param case_root: path of the working folder for the use case
    :param subs_id_file_n: Number of input files to consolidate
    :return: analytical report
    """
    # Initialize DF
    subs = pd.DataFrame()

    print('Read subsidiary input tables')

    # Read ORBIS input list for subsidiaries
    for number in list(range(1, subs_id_file_n + 1)):
        print('File #' + str(number) + '/' + str(subs_id_file_n))
        df = pd.read_excel(case_root.joinpath(r'input\listed companies subsidiaries #' + str(number) + '.xlsx'),
                           sheet_name='Results',
                           na_values='No data fulfill your filter criteria',
                           names=['rank', 'company_name', 'bvd9', 'bvd_id', 'group_subs_Count', 'sub_company_name',
                                  'sub_bvd9', 'sub_bvd_id', 'subs_lvl'],
                           dtype={
                               **{col: str for col in
                                  ['rank', 'company_name', 'bvd9', 'bvd_id', 'subsidiary_name', 'sub_bvd9',
                                   'sub_bvd_id']},
                               'group_subs_Count': pd.Int64Dtype(),
                               'subs_lvl': pd.Int8Dtype()}
                           ).drop(columns=['rank', 'subs_lvl', 'group_subs_Count'])

        # Consolidate list of subsidiaries
        subs = subs.append(df)

    # Drops not bvd identified subsidiaries and (group,subs) duplicates
    subs_clean = subs.dropna(subset=['bvd9', 'sub_bvd9']).drop_duplicates(['bvd9', 'sub_bvd9'], keep='first')

    report = pd.DataFrame({'Selected_bvd9': subs['bvd9'].nunique(),
                           'Selected_sub_bvd9': subs_clean['sub_bvd9'].nunique(),
                           'Duplicate_sub_bvd9': subs_clean.duplicated(subset='sub_bvd9', keep=False).sum()
                           }, index=['Initial set'])

    print('Save subsidiaries output file ...')

    # Save it as csv
    subs_clean.to_csv(case_root.joinpath(r'listed companies subsidiaries.csv'),
                      index=False,
                      columns=['company_name', 'bvd9', 'bvd_id', 'sub_company_name', 'sub_bvd9', 'sub_bvd_id'
                               ],
                      na_rep='n.a.'
                      )

    return report


def load_subs_fin(case_root, subs_fin_file_n, select_subs, country_map):
    """
    Loads financials for subsidiaries
    :param case_root: path of the working folder for the use case
    :param year_lastav: most recent year to consider for R&D expenditures
    :param subs_fin_file_n: Number of input files to consolidate
    :return: Analytical report
    """
    subs_fin = pd.DataFrame()
    report = pd.DataFrame()

    print('Read subsidiaries financials input tables')

    # Read ORBIS input list for subsidiaries financials
    for number in list(range(1, subs_fin_file_n + 1)):
        print('File #' + str(number) + '/' + str(subs_fin_file_n))
        df = pd.read_excel(
            case_root.joinpath(r'input\listed companies subsidiaries - financials #' + str(number) + '.xlsx'),
            sheet_name='Results',
            names=['rank', 'sub_company_name', 'sub_bvd9', 'sub_bvd_id', 'country_iso', 'NACE_code', 'NACE_desc',
                   'year_lastavail']
                  + ['operating_revenue_y' + str(YY) for YY in range(10, 20)[::-1]]
                  + ['trade_desc', 'products&services_desc', 'full_overview_desc'],
            na_values='n.a.',
            dtype={
                **{col: str for col in
                   ['sub_company_name', 'sub_bvd9', 'sub_bvd_id', 'country_iso', 'NACE_code', 'NACE_desc',
                    'trade_desc', 'products&services_desc', 'full_overview_desc']},
                **{col: float for col in ['operating_revenue_y' + str(YY) for YY in range(10, 20)[::-1]]}
            }
        ).drop(columns=['rank', 'NACE_code', 'NACE_desc', 'year_lastavail'])

        # Consolidate subsidiaries financials
        subs_fin = subs_fin.append(df)

    report = report.append(
        pd.DataFrame(
            {'Selected_bvd9': 'n.a.',
             'Selected_sub_ bvd9': subs_fin['sub_bvd9'].count().sum(),
             'Duplicate_sub_bvd9': subs_fin['sub_bvd9'].duplicated().sum()
             }, index=['From input files']
        ))

    subs_fin = subs_fin.drop_duplicates('sub_bvd9').dropna(subset=['operating_revenue_y' + str(YY) for YY in range(10, 20)[::-1]],
                                                           how='all')

    report = report.append(
        pd.DataFrame(
            {'Selected_bvd9': 'n.a.',
             'Selected_sub_ bvd9': subs_fin['sub_bvd9'].count().sum(),
             'Duplicate_sub_bvd9': subs_fin['sub_bvd9'].duplicated().sum()
             }, index=['With financials']
        ))

    subs_fin = subs_fin[subs_fin['sub_bvd9'].isin(select_subs['sub_bvd9'])]

    report = report.append(
        pd.DataFrame(
            {'Selected_bvd9': 'n.a.',
             'Selected_sub_ bvd9': subs_fin['sub_bvd9'].count().sum(),
             'Duplicate_sub_bvd9': subs_fin['sub_bvd9'].duplicated().sum()
             }, index=['In select_subs']
        ))

    # Merging subsidiary country_map for allocation to world player categories and countries
    merged = pd.merge(
        subs_fin, country_map[['country_2DID_iso', 'country_3DID_iso', 'world_player']],
        left_on='country_iso', right_on='country_2DID_iso',
        how='left',
        suffixes=(False, False)
    )

    # Save it as csv
    merged.to_csv(case_root.joinpath(r'listed companies subsidiaries - financials.csv'),
                  index=False,
                  float_format='%.10f',
                  na_rep='n.a.'
                  )

    return report


def filter_comps_and_subs(case_root, select_subs, subs_fin):
    """
    Add bolean masks for the implementation of different rnd calculation method
    keep_all: Keep all main companies and all subsidiaries
    keep_comps: Keep all main companies and exclude subsidiaries that are main companies from subsidiaries list
    keep_subs: Exclude main companies that are a subsidiary from companies list and keep all subsidiaries
    :param case_root: path of the working folder for the use case
    :param select_subs: Consolidated dataframe of subsidiary identification and mapping to companies
    :return: analytical report
    """
    report = pd.DataFrame()

    print('Screen companies and subsidiaries lists')

    # Flag main companies that are a subsidiary of another main company and vice versa
    select_subs['is_comp_a_sub'] = select_subs['bvd9'].isin(select_subs['sub_bvd9'])
    select_subs['is_sub_a_comp'] = select_subs['sub_bvd9'].isin(select_subs['bvd9'])
    select_subs['has_fin'] = select_subs['sub_bvd9'].isin(subs_fin['sub_bvd9'])

    # Flag subsidiaries that are subsidiaries of multiple main companies
    select_subs['is_sub_a_duplicate'] = select_subs.duplicated(subset='sub_bvd9', keep=False)

    print('Flag Keep all strategy')

    # Keep all main companies and all subsidiaries
    select_subs['keep_all'] = True

    report = report.append(
        pd.DataFrame({'Selected_bvd9': select_subs['bvd9'][select_subs['keep_all'] == True].nunique(),
                      'Selected_sub_bvd9': select_subs['sub_bvd9'][select_subs['keep_all'] == True].nunique(),
                      'sub_bvd9_w_fin': select_subs['has_fin'][select_subs['keep_all'] == True].sum(),
                      'Dup_sub_bvd9w_fin': select_subs['is_sub_a_duplicate'][
                          (select_subs['keep_all'] == True) & (select_subs['has_fin'] == True)].sum()
                      }, index=['keep_all']))

    print('Flag Keep comps strategy')

    # Keep all main companies and exclude subsidiaries that are main companies from subsidiaries list
    select_subs['keep_comps'] = select_subs['is_sub_a_comp'] == False

    report = report.append(
        pd.DataFrame({'Selected_bvd9': select_subs['bvd9'][select_subs['keep_comps'] == True].nunique(),
                      'Selected_sub_bvd9': select_subs['sub_bvd9'][
                          select_subs['keep_comps'] == True].nunique(),
                      'sub_bvd9_w_fin': select_subs['has_fin'][select_subs['keep_comps'] == True].sum(),
                      'Dup_sub_bvd9w_fin': select_subs['is_sub_a_duplicate'][
                          (select_subs['keep_comps'] == True) & (select_subs['has_fin'] == True)].sum()
                      }, index=['keep_comps']))

    print('Flag Keep subs strategy')

    # Exclude main companies that are a subsidiary from companies list and keep all subsidiaries
    select_subs['keep_subs'] = select_subs['is_comp_a_sub'] == False

    report = report.append(
        pd.DataFrame({'Selected_bvd9': select_subs['bvd9'][select_subs['keep_subs'] == True].nunique(),
                      'Selected_sub_bvd9': select_subs['sub_bvd9'][
                          select_subs['keep_subs'] == True].nunique(),
                      'sub_bvd9_w_fin': select_subs['has_fin'][select_subs['keep_subs'] == True].sum(),
                      'Dup_sub_bvd9w_fin': select_subs['is_sub_a_duplicate'][
                          (select_subs['keep_subs'] == True) & (select_subs['has_fin'] == True)].sum()
                      }, index=['Keep_subs']))

    print('Save companies and subsidiaries output files with filters ...')

    # Merging subsidiary country_map for allocation to world player categories and countries
    merged = pd.merge(
        select_subs, subs_fin[['sub_bvd9', 'country_3DID_iso', 'world_player']],
        left_on='sub_bvd9', right_on='sub_bvd9',
        how='left',
        suffixes=(False, False)
    )

    # Save it as csv
    merged.to_csv(case_root.joinpath(r'listed companies subsidiaries - methods.csv'),
                  index=False,
                  na_rep='n.a.'
                  )

    return report


def screen_subs(case_root, keywords, subs_fin):
    categories = list(keywords.keys())

    for category in categories:

        subs_fin[category] = False

        for keyword in keywords[category]:
            subs_fin[category] |= subs_fin['trade_desc'].str.contains(keyword, case=False, regex=False) | \
                                  subs_fin['products&services_desc'].str.contains(keyword, case=False, regex=False) | \
                                  subs_fin['full_overview_desc'].str.contains(keyword, case=False, regex=False)

    screen_subs = subs_fin.loc[:, ['sub_company_name', 'sub_bvd9', 'sub_bvd_id'] + categories]

    screen_subs['sub_turnover'] = subs_fin.loc[:, ['operating_revenue_y' + str(YY) for YY in range(10, 20)]].sum(axis=1)

    screen_subs['keyword_mask'] = list(
        map(bool, subs_fin[[cat for cat in categories if cat not in ['generation', 'rnd']]].sum(axis=1)))

    screen_subs['sub_turnover_masked'] = screen_subs['sub_turnover'].mask(~screen_subs['keyword_mask'])

    report = pd.DataFrame({'#subs': subs_fin['sub_bvd9'].count().sum(),
                           '#subs matching keywords': screen_subs.loc[
                               screen_subs['keyword_mask'] == True, 'sub_bvd9'].count().sum()
                           }, index=['Keyword'])

    # Save it as csv
    screen_subs.to_csv(case_root.joinpath(r'listed companies subsidiaries - screening.csv'),
                       index=False,
                       columns=['sub_bvd9', 'sub_bvd_id', 'sub_company_name', 'sub_turnover_masked', 'sub_turnover',
                                'keyword_mask'] + [cat for cat in categories],
                       float_format='%.10f',
                       na_rep='n.a.'
                       )

    return report


def compute_sub_exposure(case_root, select_subs, screen_subs, method):
    # Merging selected subsidiaries by method with masked turnover and turnover
    sub_exposure = pd.merge(
        select_subs[select_subs[method] == True], screen_subs,
        left_on='sub_bvd9', right_on='sub_bvd9',
        how='left'
    ).drop(
        columns=['keep_all', 'keep_comps', 'keep_subs']
    )

    # Calculating group exposure
    main_comp_exposure = sub_exposure[
        ['bvd9', 'sub_turnover_masked', 'sub_turnover']
    ].groupby(['bvd9']).sum().rename(
        columns={'sub_turnover': 'total_sub_turnover_in_main_comp',
                 'sub_turnover_masked': 'total_sub_turnover_masked_in_main_comp'}
    )

    main_comp_exposure['main_comp_exposure'] = main_comp_exposure['total_sub_turnover_masked_in_main_comp'] / \
                                               main_comp_exposure['total_sub_turnover_in_main_comp']

    main_comp_exposure.reset_index(inplace=True)

    # Calculating subsidiary level exposure
    sub_exposure = pd.merge(
        sub_exposure, main_comp_exposure[
            ['bvd9', 'total_sub_turnover_masked_in_main_comp', 'total_sub_turnover_in_main_comp',
             'main_comp_exposure']],
        left_on='bvd9', right_on='bvd9',
        how='left'
    )

    sub_exposure['sub_exposure'] = sub_exposure['sub_turnover_masked'] / sub_exposure['total_sub_turnover_in_main_comp']

    sub_exposure.dropna(subset=['main_comp_exposure', 'sub_exposure'], inplace=True)

    # Save output tables
    main_comp_exposure.to_csv(case_root.joinpath(r'listed companies - exposure - ' + method + '.csv'),
                              index=False,
                              float_format='%.10f',
                              na_rep='n.a.',
                              columns=['bvd9', 'total_sub_turnover_masked_in_main_comp',
                                       'total_sub_turnover_in_main_comp', 'main_comp_exposure']
                              )

    sub_exposure.to_csv(case_root.joinpath(r'listed companies subsidiaries - exposure - ' + method + '.csv'),
                        index=False,
                        float_format='%.10f',
                        na_rep='n.a.',
                        columns=['bvd9', 'company_name', 'total_sub_turnover_masked_in_main_comp',
                                 'total_sub_turnover_in_main_comp', 'main_comp_exposure', 'sub_bvd9',
                                 'sub_company_name', 'sub_turnover', 'sub_turnover_masked', 'sub_exposure'
                                 ]
                        )


def compute_main_comp_rnd(case_root, main_comp_exposure, main_comp_fin, method):
    # Calculating group level rnd
    main_comp_rnd = pd.merge(
        main_comp_exposure[['bvd9', 'main_comp_exposure']], main_comp_fin,
        left_on='bvd9', right_on='bvd9',
        how='left'
    )

    main_comp_rnd = main_comp_rnd.melt(id_vars=['bvd9', 'main_comp_exposure', 'company_name'],
                                       value_vars=['rnd_y' + str(YY) for YY in range(10, 20)[::-1]],
                                       var_name='rnd_label', value_name='main_comp_rnd')

    main_comp_rnd['year'] = [int('20' + s[-2:]) for s in main_comp_rnd['rnd_label']]

    main_comp_rnd['main_comp_rnd_' + method] = main_comp_rnd['main_comp_rnd'] * main_comp_rnd['main_comp_exposure']

    main_comp_rnd.dropna(subset=['main_comp_exposure', 'main_comp_rnd', 'main_comp_rnd_' + method], how='any',
                         inplace=True)

    main_comp_rnd.to_csv(case_root.joinpath(r'listed companies - rnd estimates - ' + method + '.csv'),
                         index=False,
                         columns=['bvd9', 'company_name', 'main_comp_exposure', 'year', 'main_comp_rnd',
                                  'main_comp_rnd_' + method
                                  ],
                         float_format='%.10f',
                         na_rep='n.a.'
                         )


def compute_sub_rnd(case_root, sub_exposure, main_comp_rnd, method):
    # Calculating subsidiary level rnd
    sub_rnd = pd.merge(
        sub_exposure, main_comp_rnd[['bvd9', 'main_comp_rnd', 'year', 'main_comp_rnd_' + method]],
        left_on='bvd9', right_on='bvd9',
        how='left'
    )

    df = sub_rnd[
        ['bvd9', 'year', 'sub_exposure']
    ].groupby(['bvd9', 'year']).sum().rename(
        columns={'sub_exposure': 'main_comp_exposure_from_sub'}
    )

    sub_rnd = pd.merge(
        sub_rnd, df,
        left_on=['bvd9', 'year'], right_on=['bvd9', 'year'],
        how='left',
        suffixes=(False, False)
    )

    sub_rnd['sub_rnd_' + method] = sub_rnd['main_comp_rnd_' + method] * sub_rnd['sub_exposure'] / sub_rnd[
        'main_comp_exposure_from_sub']

    # Save output tables
    sub_rnd.to_csv(case_root.joinpath(r'listed companies subsidiaries - rnd estimates - ' + method + '.csv'),
                   index=False,
                   columns=['bvd9', 'company_name', 'total_sub_turnover_masked_in_main_comp',
                            'total_sub_turnover_in_main_comp',
                            'main_comp_exposure_from_sub', 'year', 'main_comp_rnd', 'main_comp_rnd_' + method,
                            'sub_bvd9', 'sub_company_name', 'sub_turnover', 'sub_turnover_masked', 'sub_exposure',
                            'sub_rnd_' + method
                            ],
                   float_format='%.10f',
                   na_rep='n.a.'
                   )
